"""Optional OpenGL ray-marched canvas for TIF volume preview."""

from __future__ import annotations

import math
import os
import time
from collections import OrderedDict
from dataclasses import dataclass

os.environ.setdefault("__NV_PRIME_RENDER_OFFLOAD", "1")
os.environ.setdefault("__GLX_VENDOR_LIBRARY_NAME", "nvidia")

import numpy as np

try:
    from AntSleap.core.tif_transfer_function import TRANSFER_PRESET_IDS, build_transfer_lut, normalize_transfer_function
    from AntSleap.ui.style import normalize_theme
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from core.tif_transfer_function import TRANSFER_PRESET_IDS, build_transfer_lut, normalize_transfer_function
    from ui.style import normalize_theme

GPU_VOLUME_MAX_TEXTURE_DIM = 4096
GPU_VOLUME_MAX_RAY_STEPS = 4096
GPU_VOLUME_TRANSFER_LUT_SIZE = 256
GPU_VOLUME_TEXTURE_CACHE_DEFAULT_BUDGET_BYTES = 5 * 1024 * 1024 * 1024
GPU_VOLUME_RENDER_MODES = {
    "composite": 0,
    "mip": 1,
    "minip": 2,
    "average": 3,
    "surface": 4,
}
GPU_VOLUME_MASK_MODES = {
    "image_only": 0,
    "mask_boundary": 1,
    "masked_image": 2,
}
GPU_PREVIEW_BUILD_BACKEND_UNAVAILABLE = "unavailable"
GPU_PREVIEW_BUILD_BACKEND_FRAGMENT = "fragment"
GPU_PREVIEW_BUILD_BACKEND_COMPUTE = "compute"
GPU_VOLUME_STREAM_BUILD_DEFAULT_STAGING_BYTES = 128 * 1024 * 1024
GPU_VOLUME_STREAM_BUILD_MIN_DIM = 128
GPU_VOLUME_COMPUTE_LOCAL_SIZE = (8, 8, 4)
GPU_VOLUME_DARK_CLEAR_RGB = (0.027, 0.063, 0.114)
GPU_VOLUME_LIGHT_CLEAR_RGB = (0.067, 0.102, 0.169)

_COMPUTE_COPY_SHADER_TEMPLATE = """
#version 430

layout(local_size_x = 8, local_size_y = 8, local_size_z = 4) in;

uniform sampler3D u_source;
uniform ivec3 u_source_shape;
uniform ivec3 u_target_slab_shape;
uniform ivec3 u_factors;
uniform int u_algorithm;
uniform int u_apply_window;
uniform vec2 u_window;
uniform int u_z_offset;

layout(__IMAGE_FORMAT__, binding = 0) writeonly uniform image3D u_dest;

float normalized_output(float value)
{
    if (u_apply_window == 0) {
        return clamp(value, 0.0, 1.0);
    }
    float width = max(u_window.y - u_window.x, 0.000001);
    return clamp((value - u_window.x) / width, 0.0, 1.0);
}

void main()
{
    ivec3 local_pos = ivec3(gl_GlobalInvocationID.xyz);
    if (
        local_pos.x >= u_target_slab_shape.x ||
        local_pos.y >= u_target_slab_shape.y ||
        local_pos.z >= u_target_slab_shape.z
    ) {
        return;
    }
    ivec3 block_start = ivec3(local_pos.x * u_factors.x, local_pos.y * u_factors.y, local_pos.z * u_factors.z);
    ivec3 block_end = min(block_start + u_factors, u_source_shape);
    block_start = clamp(block_start, ivec3(0), max(u_source_shape - ivec3(1), ivec3(0)));
    block_end = max(block_end, block_start + ivec3(1));

    float value = 0.0;
    if (u_algorithm == 0) {
        value = texelFetch(u_source, block_start, 0).r;
    } else {
        float sum_value = 0.0;
        float max_value = 0.0;
        int sample_count = 0;
        for (int z = block_start.z; z < block_end.z; ++z) {
            for (int y = block_start.y; y < block_end.y; ++y) {
                for (int x = block_start.x; x < block_end.x; ++x) {
                    float sample_value = texelFetch(u_source, ivec3(x, y, z), 0).r;
                    sum_value += sample_value;
                    max_value = max(max_value, sample_value);
                    sample_count += 1;
                }
            }
        }
        float mean_value = sum_value / float(max(sample_count, 1));
        if (u_algorithm == 1) {
            value = mean_value;
        } else if (u_algorithm == 2) {
            value = max_value;
        } else {
            value = mean_value * 0.65 + max_value * 0.35;
        }
    }
    value = normalized_output(value);
    imageStore(u_dest, ivec3(local_pos.x, local_pos.y, local_pos.z + u_z_offset), vec4(value, 0.0, 0.0, 1.0));
}
"""

def _gpu_texture_cache_budget_bytes():
    value = os.environ.get("TAXAMASK_TIF_GPU_TEXTURE_CACHE_GB", "").strip()
    if value:
        try:
            gb = float(value)
            if gb <= 0:
                return 0
            return int(gb * 1024 * 1024 * 1024)
        except (TypeError, ValueError):
            pass
    return int(GPU_VOLUME_TEXTURE_CACHE_DEFAULT_BUDGET_BYTES)


def _volume_overlay_color(alpha=190, theme="dark"):
    rgb = GPU_VOLUME_LIGHT_CLEAR_RGB if normalize_theme(theme) == "light" else GPU_VOLUME_DARK_CLEAR_RGB
    return QColor(
        max(0, min(255, int(round(rgb[0] * 255)))),
        max(0, min(255, int(round(rgb[1] * 255)))),
        max(0, min(255, int(round(rgb[2] * 255)))),
        max(0, min(255, int(alpha))),
    )


try:
    from PySide6.QtCore import QRect, Qt, QTimer, Signal
    from PySide6.QtGui import QColor, QImage, QOffscreenSurface, QOpenGLContext, QPainter, QPen, QPixmap, QSurfaceFormat
    from PySide6.QtWidgets import QFrame, QLabel
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
except Exception as exc:  # pragma: no cover - exercised only on partial Qt installs
    QFrame = None
    QImage = None
    QLabel = None
    QOpenGLWidget = None
    QOffscreenSurface = None
    QOpenGLContext = None
    QColor = None
    QPainter = None
    QPen = None
    QPixmap = None
    QSurfaceFormat = None
    _QT_OPENGL_IMPORT_ERROR = exc
else:
    _QT_OPENGL_IMPORT_ERROR = None

try:
    from OpenGL import GL
except Exception as exc:  # pragma: no cover - depends on optional runtime package
    GL = None
    _PYOPENGL_IMPORT_ERROR = exc
else:
    _PYOPENGL_IMPORT_ERROR = None


_VERTEX_SHADER = """
#version 120
attribute vec2 a_position;
varying vec2 v_uv;

void main()
{
    v_uv = a_position * 0.5 + 0.5;
    gl_Position = vec4(a_position, 0.0, 1.0);
}
"""


_FRAGMENT_SHADER = """
#version 120
varying vec2 v_uv;

uniform sampler3D u_volume;
uniform sampler3D u_mask;
uniform sampler2D u_transfer_lut;
uniform mat3 u_inv_rotation;
uniform vec3 u_shape_scale;
uniform vec2 u_viewport;
uniform vec2 u_pan;
uniform float u_cutoff;
uniform float u_zoom;
uniform float u_camera_distance;
uniform float u_front_clip;
uniform float u_step_size;
uniform float u_opacity;
uniform float u_gradient_weight;
uniform float u_clarity;
uniform float u_mask_opacity;
uniform float u_enhancement;
uniform float u_tone_gamma;
uniform float u_jitter_strength;
uniform float u_adaptive_step_strength;
uniform float u_gradient_opacity;
uniform vec2 u_gradient_opacity_range;
uniform vec3 u_tint_rgb;
uniform vec3 u_clip_plane_normal;
uniform float u_clip_plane_depth;
uniform vec3 u_texel_step;
uniform int u_steps;
uniform int u_projection_mode;
uniform int u_mask_mode;
uniform int u_clip_plane_enabled;
uniform int u_surface_refine;
uniform int u_fast_interaction;

const int MAX_RAY_STEPS = __MAX_RAY_STEPS__;

float safe_component(float value)
{
    if (abs(value) < 0.000001) {
        return value < 0.0 ? -0.000001 : 0.000001;
    }
    return value;
}

vec2 intersect_box(vec3 ray_origin, vec3 ray_direction, vec3 half_size)
{
    vec3 safe_direction = vec3(
        safe_component(ray_direction.x),
        safe_component(ray_direction.y),
        safe_component(ray_direction.z)
    );
    vec3 t0 = (-half_size - ray_origin) / safe_direction;
    vec3 t1 = (half_size - ray_origin) / safe_direction;
    vec3 tmin = min(t0, t1);
    vec3 tmax = max(t0, t1);
    float near_hit = max(max(tmin.x, tmin.y), tmin.z);
    float far_hit = min(min(tmax.x, tmax.y), tmax.z);
    return vec2(near_hit, far_hit);
}

vec4 transfer_sample(float density)
{
    return texture2D(u_transfer_lut, vec2(clamp(density, 0.0, 1.0), 0.5));
}

float volume_sample(vec3 texcoord)
{
    return texture3D(u_volume, clamp(texcoord, vec3(0.0), vec3(1.0))).r;
}

float mask_sample(vec3 texcoord)
{
    return texture3D(u_mask, clamp(texcoord, vec3(0.0), vec3(1.0))).r;
}

vec3 central_gradient(vec3 texcoord, vec3 texel_step)
{
    float vx = volume_sample(texcoord + vec3(texel_step.x, 0.0, 0.0)) -
               volume_sample(texcoord - vec3(texel_step.x, 0.0, 0.0));
    float vy = volume_sample(texcoord + vec3(0.0, texel_step.y, 0.0)) -
               volume_sample(texcoord - vec3(0.0, texel_step.y, 0.0));
    float vz = volume_sample(texcoord + vec3(0.0, 0.0, texel_step.z)) -
               volume_sample(texcoord - vec3(0.0, 0.0, texel_step.z));
    return vec3(vx, vy, vz);
}

vec3 tetra_gradient(vec3 texcoord, vec3 texel_step)
{
    vec2 k = vec2(1.0, -1.0);
    vec3 grad = k.xyy * volume_sample(texcoord + k.xyy * texel_step) +
                k.yyx * volume_sample(texcoord + k.yyx * texel_step) +
                k.yxy * volume_sample(texcoord + k.yxy * texel_step) +
                k.xxx * volume_sample(texcoord + k.xxx * texel_step);
    return grad * 0.5;
}

vec3 clip_plane_normal()
{
    return normalize(u_clip_plane_normal + vec3(0.000001, 0.0, 0.0));
}

float clip_plane_extent(vec3 normal, vec3 half_size)
{
    return max(dot(abs(normal), half_size), 0.0001);
}

float clip_plane_offset(vec3 normal, vec3 half_size)
{
    float extent = clip_plane_extent(normal, half_size);
    return mix(extent, -extent, clamp(u_clip_plane_depth, 0.0, 1.0));
}

bool clip_plane_discards(vec3 point, vec3 normal, float offset)
{
    if (u_clip_plane_enabled == 0) {
        return false;
    }
    return dot(point, normal) > offset;
}

float mask_boundary_sample(vec3 texcoord, vec3 texel_step)
{
    float center = mask_sample(texcoord);
    if (center <= 0.5) {
        return 0.0;
    }
    float neighbor_min = 1.0;
    neighbor_min = min(neighbor_min, mask_sample(texcoord + vec3(texel_step.x, 0.0, 0.0)));
    neighbor_min = min(neighbor_min, mask_sample(texcoord - vec3(texel_step.x, 0.0, 0.0)));
    neighbor_min = min(neighbor_min, mask_sample(texcoord + vec3(0.0, texel_step.y, 0.0)));
    neighbor_min = min(neighbor_min, mask_sample(texcoord - vec3(0.0, texel_step.y, 0.0)));
    neighbor_min = min(neighbor_min, mask_sample(texcoord + vec3(0.0, 0.0, texel_step.z)));
    neighbor_min = min(neighbor_min, mask_sample(texcoord - vec3(0.0, 0.0, texel_step.z)));
    return 1.0 - step(0.5, neighbor_min);
}

vec4 section_plane_color(vec3 texcoord, vec3 texel_step, float mask_value)
{
    float sample_value = volume_sample(texcoord);
    if (sample_value <= 0.001) {
        return vec4(0.0);
    }
    if (u_mask_mode == 2 && mask_value <= 0.5) {
        return vec4(0.0);
    }
    float section_cutoff = clamp(u_cutoff * 0.28, 0.0, 0.72);
    float density = clamp((sample_value - section_cutoff) / max(1.0 - section_cutoff, 0.001), 0.0, 1.0);
    vec3 grad = central_gradient(texcoord, texel_step);
    float edge = smoothstep(0.035, 0.25, length(grad) * 11.5);
    float section_surface = max(edge, smoothstep(0.08, 0.46, density));
    vec4 transfer = transfer_sample(max(density, edge * 0.42));
    vec3 normal = normalize(grad + vec3(0.0001));
    vec3 light_dir = normalize(vec3(0.45, 0.58, 0.68));
    float diffuse = max(dot(normal, light_dir), 0.0);
    vec3 gray = vec3(pow(clamp(density, 0.0, 1.0), 0.82 * max(0.60, u_tone_gamma)));
    vec3 tint = normalize(max(u_tint_rgb, vec3(0.001)));
    vec3 color = mix(gray * tint * 0.72, transfer.rgb, 0.74) * (0.68 + 0.24 * diffuse + 0.22 * density);
    color += transfer.rgb * edge * mix(0.18, 0.32, clamp(u_clarity, 0.0, 1.0));
    if (u_mask_mode == 1) {
        float boundary = mask_boundary_sample(texcoord, texel_step);
        color = mix(color, vec3(1.0, 0.56, 0.26), clamp(u_mask_opacity, 0.0, 1.0) * boundary);
        edge = max(edge, boundary);
    }
    float alpha = clamp((0.42 + pow(density, 0.55) * 0.24 + edge * 0.28 + transfer.a * 0.08) * max(section_surface, 0.48), 0.0, 0.88);
    return vec4(clamp(color, 0.0, 1.0), alpha);
}

float front_clip_start_t(float ray_start, float ray_end)
{
    return mix(ray_start, ray_end, clamp(u_front_clip, 0.0, 0.92));
}

float hash12(vec2 p)
{
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

void main()
{
    vec2 centered = v_uv * 2.0 - 1.0;
    centered.x *= u_viewport.x / max(u_viewport.y, 1.0);
    centered -= u_pan;

    vec3 camera_origin = vec3(centered / max(u_zoom, 0.001), u_camera_distance);
    vec3 camera_direction = vec3(0.0, 0.0, -1.0);
    vec3 ray_origin = u_inv_rotation * camera_origin;
    vec3 ray_direction = normalize(u_inv_rotation * camera_direction);
    vec3 half_size = u_shape_scale * 0.5;
    vec3 plane_normal = clip_plane_normal();
    float plane_offset = clip_plane_offset(plane_normal, half_size);

    vec2 hit = intersect_box(ray_origin, ray_direction, half_size);
    if (hit.x > hit.y || hit.y < 0.0) {
        gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }

    float ray_start = max(hit.x, 0.0);
    float ray_end = hit.y;
    float t = front_clip_start_t(ray_start, ray_end);
    float jitter = (hash12(gl_FragCoord.xy) - 0.5) * u_step_size * clamp(u_jitter_strength, 0.0, 1.0);
    t = clamp(t + jitter, ray_start, ray_end);
    vec4 accum = vec4(0.0);
    vec4 section_accum = vec4(0.0);
    float first_depth = 0.0;
    float got_first_hit = 0.0;
    float mip_density = 0.0;
    float mip_depth = 0.0;
    float min_value = 1.0;
    float got_min = 0.0;
    float average_density = 0.0;
    float average_count = 0.0;
    float projected_boundary = 0.0;
    vec3 texel_step = max(u_texel_step, vec3(0.0005));
    vec3 light_dir = normalize(vec3(0.45, 0.58, 0.68));
    vec3 view_dir = normalize(-ray_direction);
    vec3 boundary_color = vec3(1.0, 0.56, 0.26);

    if (u_clip_plane_enabled > 0) {
        float plane_denom = dot(ray_direction, plane_normal);
        if (abs(plane_denom) > 0.000001) {
            float plane_t = (plane_offset - dot(ray_origin, plane_normal)) / plane_denom;
            if (plane_t >= t && plane_t <= ray_end) {
                vec3 plane_point = ray_origin + ray_direction * plane_t;
                vec3 plane_texcoord = plane_point / u_shape_scale + 0.5;
                if (
                    plane_texcoord.x >= 0.0 && plane_texcoord.x <= 1.0 &&
                    plane_texcoord.y >= 0.0 && plane_texcoord.y <= 1.0 &&
                    plane_texcoord.z >= 0.0 && plane_texcoord.z <= 1.0
                ) {
                    float plane_mask = 1.0;
                    if (u_mask_mode > 0) {
                        plane_mask = mask_sample(plane_texcoord);
                    }
                    vec4 section = section_plane_color(plane_texcoord, texel_step, plane_mask);
                    if (section.a > 0.001) {
                        section_accum = section;
                    }
                    t = max(t, plane_t + max(u_step_size * 0.75, 0.0005));
                }
            }
        }
    }

    for (int i = 0; i < MAX_RAY_STEPS; ++i) {
        if (i >= u_steps || t > hit.y) {
            break;
        }
        vec3 point = ray_origin + ray_direction * t;
        if (clip_plane_discards(point, plane_normal, plane_offset)) {
            t += u_step_size;
            continue;
        }
        vec3 texcoord = point / u_shape_scale + 0.5;
        float sample_value = volume_sample(texcoord);
        float mask_value = 1.0;
        float mask_boundary = 0.0;
        if (u_mask_mode > 0) {
            mask_value = mask_sample(texcoord);
            if (u_mask_mode == 2 && mask_value <= 0.5) {
                t += u_step_size;
                continue;
            }
            if (u_mask_mode == 1) {
                mask_boundary = mask_boundary_sample(texcoord, texel_step);
                projected_boundary = max(projected_boundary, mask_boundary);
            }
        }
        float density = clamp((sample_value - u_cutoff) / max(1.0 - u_cutoff, 0.001), 0.0, 1.0);
        if (
            u_adaptive_step_strength > 0.0 &&
            u_fast_interaction == 0 &&
            u_projection_mode == 0 &&
            u_mask_mode == 0 &&
            u_clip_plane_enabled == 0 &&
            sample_value <= 0.001
        ) {
            t += u_step_size * mix(1.0, 2.25, clamp(u_adaptive_step_strength, 0.0, 1.0));
            continue;
        }
        if (u_projection_mode == 1) {
            if (density > mip_density) {
                mip_density = density;
                mip_depth = 1.0 - float(i) / max(float(u_steps), 1.0);
            }
            t += u_step_size;
            continue;
        }
        if (u_projection_mode == 2) {
            if (sample_value > 0.001) {
                min_value = min(min_value, sample_value);
                got_min = 1.0;
            }
            t += u_step_size;
            continue;
        }
        if (u_projection_mode == 3) {
            average_density += density;
            average_count += 1.0;
            t += u_step_size;
            continue;
        }
        if (density > 0.001 || mask_boundary > 0.0) {
            vec4 transfer = transfer_sample(max(density, mask_boundary * 0.35));
            if (transfer.a <= 0.001) {
                t += u_step_size;
                continue;
            }
            vec3 transfer_color = transfer.rgb;
            if (u_mask_mode == 1 && mask_boundary > 0.0) {
                transfer_color = mix(transfer_color, boundary_color, clamp(u_mask_opacity, 0.0, 1.0) * mask_boundary);
            }
            if (u_fast_interaction > 0 && u_projection_mode == 0) {
                float alpha = clamp(pow(density, 1.05) * transfer.a * u_opacity * 0.18, 0.0, 0.34);
                if (got_first_hit < 0.5 && alpha > 0.002) {
                    first_depth = 1.0 - float(i) / max(float(u_steps), 1.0);
                    got_first_hit = 1.0;
                }
                vec3 shaded = transfer_color * (0.58 + 0.42 * density);
                accum.rgb += (1.0 - accum.a) * shaded * alpha;
                accum.a += (1.0 - accum.a) * alpha;
                if (accum.a > 0.94) {
                    break;
                }
                t += u_step_size;
                continue;
            }

            float detail = clamp(u_enhancement, 0.0, 1.0);
            vec3 grad = mix(central_gradient(texcoord, texel_step), tetra_gradient(texcoord, texel_step * 1.15), detail);
            float grad_mag = clamp(length(grad) * mix(6.5, 8.8, detail), 0.0, 1.0);
            float detail_edge = smoothstep(0.10, 0.48, grad_mag) * detail;
            float gradient_alpha = smoothstep(u_gradient_opacity_range.x, u_gradient_opacity_range.y, grad_mag) * clamp(u_gradient_opacity, 0.0, 1.0);
            vec3 normal = normalize(grad + vec3(0.0001));
            float diffuse = max(dot(normal, light_dir), 0.0);
            float rim = pow(1.0 - max(dot(normal, view_dir), 0.0), 2.0);
            float spec = pow(max(dot(reflect(-light_dir, normal), view_dir), 0.0), 24.0);

            float surface = smoothstep(0.05, 0.35, grad_mag) * u_gradient_weight;
            surface = max(surface, gradient_alpha * 0.82);
            surface = max(surface, detail_edge * 0.36);
            surface = max(surface, mask_boundary * clamp(u_mask_opacity, 0.0, 1.0) * 0.55);
            if (u_projection_mode == 4) {
                if (density > 0.035 || surface > 0.08) {
                    float surface_alpha = clamp(max(max(density, surface), gradient_alpha * 0.72) * transfer.a, 0.0, 1.0);
                    vec3 shaded_surface = transfer_color * (0.44 + 0.50 * diffuse) + transfer_color * rim * 0.22 + vec3(spec * 0.46);
                    if (u_clarity > 0.0) {
                        surface_alpha = clamp(max(surface * 1.12, density * 0.92) * max(transfer.a, 0.38), 0.0, 1.0);
                        shaded_surface = mix(
                            shaded_surface,
                            transfer_color * (0.36 + 0.58 * diffuse) + vec3(detail_edge * 0.22) + vec3(spec * 0.34),
                            0.55
                        );
                    }
                    float hit_t = t;
                    if (u_surface_refine > 0 && detail > 0.0) {
                        float low_t = max(ray_start, t - u_step_size);
                        float high_t = t;
                        for (int b = 0; b < 5; ++b) {
                            float mid_t = (low_t + high_t) * 0.5;
                            vec3 mid_point = ray_origin + ray_direction * mid_t;
                            if (clip_plane_discards(mid_point, plane_normal, plane_offset)) {
                                low_t = mid_t;
                            } else {
                                vec3 mid_texcoord = mid_point / u_shape_scale + 0.5;
                                float mid_density = clamp((volume_sample(mid_texcoord) - u_cutoff) / max(1.0 - u_cutoff, 0.001), 0.0, 1.0);
                                if (mid_density > 0.035) {
                                    high_t = mid_t;
                                } else {
                                    low_t = mid_t;
                                }
                            }
                        }
                        hit_t = high_t;
                    }
                    accum = vec4(shaded_surface * (0.80 + 0.20 * surface_alpha), surface_alpha);
                    first_depth = 1.0 - clamp((hit_t - ray_start) / max(ray_end - ray_start, 0.0001), 0.0, 1.0);
                    got_first_hit = 1.0;
                    break;
                }
                t += u_step_size;
                continue;
            }
            float normal_opacity = pow(density, 1.22) * 18.0 + surface * pow(density, 0.55) * 24.0;
            float clarity_opacity = pow(density, 1.55) * 9.0 + surface * pow(density, 0.70) * 14.0;
            float gradient_opacity_density = gradient_alpha * mix(8.0, 13.0, detail);
            float opacity_density = mix(normal_opacity, clarity_opacity, clamp(u_clarity, 0.0, 1.0)) + detail_edge * 4.5 + gradient_opacity_density;
            float alpha = 1.0 - exp(-opacity_density * u_opacity * u_step_size);
            alpha *= transfer.a;
            alpha = clamp(alpha, 0.0, mix(0.82, 0.46, clamp(u_clarity, 0.0, 1.0)));
            vec3 shaded = transfer_color * (0.50 + 0.42 * diffuse) + transfer_color * rim * mix(0.14, 0.22, u_clarity) + vec3(spec * mix(0.28, 0.42, u_clarity));
            shaded = mix(shaded, shaded * (1.0 + 0.22 * detail_edge) + vec3(0.055 * detail_edge), detail);

            if (got_first_hit < 0.5 && alpha > 0.002) {
                first_depth = 1.0 - float(i) / max(float(u_steps), 1.0);
                got_first_hit = 1.0;
            }
            accum.rgb += (1.0 - accum.a) * shaded * alpha;
            accum.a += (1.0 - accum.a) * alpha;
            if (accum.a > 0.985) {
                break;
            }
        }
        t += u_step_size;
    }

    if (u_projection_mode == 1) {
        if (mip_density <= 0.001 && projected_boundary <= 0.0) {
            if (section_accum.a > 0.001) {
                vec3 section_color = pow(clamp(section_accum.rgb * 0.88, 0.0, 1.0), vec3(0.78 * max(0.55, u_tone_gamma)));
                gl_FragColor = vec4(section_color, 1.0);
                return;
            }
            gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
            return;
        }
        vec3 color = transfer_sample(max(mip_density, projected_boundary * 0.35)).rgb;
        color *= 0.72 + 0.28 * mip_depth;
        color = mix(color, boundary_color, clamp(u_mask_opacity, 0.0, 1.0) * projected_boundary);
        if (section_accum.a > 0.001) {
            color = mix(color * 0.72, section_accum.rgb, clamp(section_accum.a * 0.68, 0.0, 0.78));
        }
        gl_FragColor = vec4(pow(clamp(color, 0.0, 1.0), vec3(0.82 * max(0.55, u_tone_gamma))), 1.0);
        return;
    }
    if (u_projection_mode == 2) {
        if (got_min < 0.5 && projected_boundary <= 0.0) {
            if (section_accum.a > 0.001) {
                vec3 section_color = pow(clamp(section_accum.rgb * 0.88, 0.0, 1.0), vec3(0.78 * max(0.55, u_tone_gamma)));
                gl_FragColor = vec4(section_color, 1.0);
                return;
            }
            gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
            return;
        }
        float inverse_value = got_min > 0.5 ? 1.0 - clamp(min_value, 0.0, 1.0) : projected_boundary * 0.35;
        vec3 color = transfer_sample(inverse_value).rgb;
        color = mix(color, boundary_color, clamp(u_mask_opacity, 0.0, 1.0) * projected_boundary);
        if (section_accum.a > 0.001) {
            color = mix(color * 0.72, section_accum.rgb, clamp(section_accum.a * 0.68, 0.0, 0.78));
        }
        gl_FragColor = vec4(pow(clamp(color, 0.0, 1.0), vec3(0.80 * max(0.55, u_tone_gamma))), 1.0);
        return;
    }
    if (u_projection_mode == 3) {
        float average_value = average_density / max(average_count, 1.0);
        if (average_value <= 0.001 && projected_boundary <= 0.0) {
            if (section_accum.a > 0.001) {
                vec3 section_color = pow(clamp(section_accum.rgb * 0.88, 0.0, 1.0), vec3(0.78 * max(0.55, u_tone_gamma)));
                gl_FragColor = vec4(section_color, 1.0);
                return;
            }
            gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
            return;
        }
        vec3 color = transfer_sample(max(average_value, projected_boundary * 0.35)).rgb;
        color = mix(color, boundary_color, clamp(u_mask_opacity, 0.0, 1.0) * projected_boundary);
        if (section_accum.a > 0.001) {
            color = mix(color * 0.72, section_accum.rgb, clamp(section_accum.a * 0.68, 0.0, 0.78));
        }
        gl_FragColor = vec4(pow(clamp(color, 0.0, 1.0), vec3(0.86 * max(0.55, u_tone_gamma))), 1.0);
        return;
    }

    if (accum.a <= 0.001) {
        if (section_accum.a > 0.001) {
            vec3 section_color = pow(clamp(section_accum.rgb * 0.88, 0.0, 1.0), vec3(0.80 * max(0.55, u_tone_gamma)));
            gl_FragColor = vec4(section_color, 1.0);
            return;
        }
        gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }
    vec3 color = accum.rgb / max(accum.a, 0.001);
    color *= 0.78 + 0.22 * first_depth;
    color = mix(color, boundary_color, clamp(u_mask_opacity, 0.0, 1.0) * projected_boundary * 0.35);
    if (section_accum.a > 0.001) {
        color = mix(color * 0.56, section_accum.rgb, clamp(section_accum.a * 0.76, 0.0, 0.88));
    }
    color = pow(clamp(color, 0.0, 1.0), vec3(0.86 * max(0.55, u_tone_gamma)));
    gl_FragColor = vec4(color, 1.0);
}
""".replace("__MAX_RAY_STEPS__", str(GPU_VOLUME_MAX_RAY_STEPS))


def gpu_volume_canvas_available():
    """Return True when the optional Qt/OpenGL imports needed by the canvas exist."""
    return QOpenGLWidget is not None and GL is not None


def gpu_volume_offscreen_available():
    """Return True when the offscreen GPU renderer can be constructed."""
    return (
        QFrame is not None
        and QOpenGLContext is not None
        and QOffscreenSurface is not None
        and QLabel is not None
        and QImage is not None
        and QPixmap is not None
        and QSurfaceFormat is not None
        and GL is not None
    )


def gpu_volume_unavailable_reason():
    if not gpu_volume_offscreen_available():
        if GL is None:
            return f"PyOpenGL is unavailable: {_PYOPENGL_IMPORT_ERROR}"
        return f"Qt offscreen OpenGL is unavailable: {_QT_OPENGL_IMPORT_ERROR}"
    if QOpenGLWidget is None:
        return f"Qt embedded OpenGL widget is unavailable: {_QT_OPENGL_IMPORT_ERROR}"
    if GL is None:
        return f"PyOpenGL is unavailable: {_PYOPENGL_IMPORT_ERROR}"
    return ""


def _shader_log(shader):
    log = GL.glGetShaderInfoLog(shader)
    if isinstance(log, bytes):
        return log.decode("utf-8", errors="replace")
    return str(log)


def _program_log(program):
    log = GL.glGetProgramInfoLog(program)
    if isinstance(log, bytes):
        return log.decode("utf-8", errors="replace")
    return str(log)


def _decode_gl_string(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _parse_gl_version(value):
    text = _decode_gl_string(value)
    is_es = "OpenGL ES" in text
    parts = text.replace("OpenGL ES", "").replace("OpenGL", "").strip().split()
    if not parts:
        return (0, 0, False)
    version = parts[0].split(".")
    try:
        major = int(version[0])
        minor = int(version[1]) if len(version) > 1 else 0
    except (TypeError, ValueError):
        return (0, 0, False)
    return (major, minor, is_es)


def _gl_integer(gl_module, name, default=0):
    try:
        value = gl_module.glGetIntegerv(name)
    except Exception:
        return default
    try:
        if isinstance(value, (list, tuple)):
            return int(value[0]) if value else default
        if hasattr(value, "flat"):
            return int(value.flat[0]) if value.size else default
        return int(value)
    except (TypeError, ValueError):
        return default


def _gl_integer_tuple(gl_module, name, count=3):
    try:
        value = gl_module.glGetIntegerv(name)
    except Exception:
        return tuple(0 for _ in range(int(count)))
    try:
        if hasattr(value, "flat"):
            values = [int(item) for item in value.flat]
        elif isinstance(value, (list, tuple)):
            values = [int(item) for item in value]
        else:
            values = [int(value)]
    except (TypeError, ValueError):
        values = []
    values = values[: int(count)]
    while len(values) < int(count):
        values.append(0)
    return tuple(values)


def _gl_extensions(gl_module):
    try:
        return _decode_gl_string(gl_module.glGetString(gl_module.GL_EXTENSIONS))
    except Exception:
        return ""


def _gl_has_extension(extensions, name):
    return str(name) in set(str(extensions or "").split())


@dataclass(frozen=True)
class GpuPreviewBuildCapabilities:
    available: bool = False
    backend: str = GPU_PREVIEW_BUILD_BACKEND_UNAVAILABLE
    reason: str = ""
    vendor: str = ""
    renderer: str = ""
    version: str = ""
    max_3d_texture_size: int = 0
    max_compute_work_group_count: tuple = (0, 0, 0)
    max_compute_work_group_size: tuple = (0, 0, 0)
    supports_compute_shader: bool = False
    supports_image_load_store: bool = False
    supports_r16_texture: bool = False
    supports_fence_sync: bool = False

    def to_stats(self):
        return {
            "available": bool(self.available),
            "backend": str(self.backend),
            "reason": str(self.reason),
            "vendor": str(self.vendor),
            "renderer": str(self.renderer),
            "version": str(self.version),
            "max_3d_texture_size": int(self.max_3d_texture_size),
            "max_compute_work_group_count": tuple(int(value) for value in self.max_compute_work_group_count),
            "max_compute_work_group_size": tuple(int(value) for value in self.max_compute_work_group_size),
            "supports_compute_shader": bool(self.supports_compute_shader),
            "supports_image_load_store": bool(self.supports_image_load_store),
            "supports_r16_texture": bool(self.supports_r16_texture),
            "supports_fence_sync": bool(self.supports_fence_sync),
        }


@dataclass(frozen=True)
class VolumePreviewTextureProvider:
    kind: str
    cache_key: object = None
    shape_zyx: tuple = ()
    dtype: str = ""
    source_shape_zyx: tuple = ()
    spacing_zyx: tuple = ()
    texture_id: int = 0
    cpu_volume: object = None
    build_backend: str = "cpu"
    estimated_bytes: int = 0

    @property
    def is_gpu_texture(self):
        return self.kind == "gpu_texture" and int(self.texture_id or 0) > 0

    @property
    def requires_upload(self):
        return self.kind == "cpu_array" and self.cpu_volume is not None

    def to_stats(self):
        return {
            "kind": str(self.kind),
            "shape_zyx": tuple(int(value) for value in self.shape_zyx),
            "dtype": str(self.dtype),
            "source_shape_zyx": tuple(int(value) for value in self.source_shape_zyx),
            "build_backend": str(self.build_backend),
            "estimated_bytes": int(self.estimated_bytes or 0),
            "is_gpu_texture": bool(self.is_gpu_texture),
            "requires_upload": bool(self.requires_upload),
        }


def cpu_volume_preview_provider(volume, source_shape=None, spacing_zyx=None, cache_key=None, build_backend="cpu"):
    source = np.asarray(volume) if volume is not None else None
    shape = tuple(int(value) for value in getattr(source, "shape", ()) or ())
    dtype = str(getattr(source, "dtype", "") or "")
    estimated_bytes = int(getattr(source, "nbytes", 0) or 0)
    return VolumePreviewTextureProvider(
        kind="cpu_array",
        cache_key=cache_key,
        shape_zyx=shape,
        dtype=dtype,
        source_shape_zyx=tuple(int(value) for value in (source_shape or shape)),
        spacing_zyx=tuple(float(value) for value in (spacing_zyx or ())),
        cpu_volume=volume,
        build_backend=str(build_backend or "cpu"),
        estimated_bytes=estimated_bytes,
    )


def gpu_texture_preview_provider(texture_id, shape_zyx, dtype, source_shape=None, spacing_zyx=None, cache_key=None, build_backend="gpu"):
    dtype_text = str(dtype or "")
    shape = tuple(int(value) for value in (shape_zyx or ()))
    bytes_per_voxel = 2 if dtype_text in {"uint16", "GL_R16", "r16"} else 1
    estimated_bytes = int(np.prod(shape)) * int(bytes_per_voxel) if len(shape) == 3 else 0
    return VolumePreviewTextureProvider(
        kind="gpu_texture",
        cache_key=cache_key,
        shape_zyx=shape,
        dtype=dtype_text,
        source_shape_zyx=tuple(int(value) for value in (source_shape or shape)),
        spacing_zyx=tuple(float(value) for value in (spacing_zyx or ())),
        texture_id=int(texture_id or 0),
        build_backend=str(build_backend or "gpu"),
        estimated_bytes=estimated_bytes,
    )


def _gl_has_attrs(gl_module, names):
    return gl_module is not None and all(hasattr(gl_module, name) for name in names)


def _volume_texture_format(dtype, gl_module=None):
    gl_module = gl_module or GL
    is_uint16 = np.dtype(dtype) == np.uint16
    if is_uint16:
        if _gl_has_attrs(gl_module, ("GL_R16", "GL_RED", "GL_UNSIGNED_SHORT")):
            return gl_module.GL_R16, gl_module.GL_RED, gl_module.GL_UNSIGNED_SHORT, "r16"
        return gl_module.GL_LUMINANCE16, gl_module.GL_LUMINANCE, gl_module.GL_UNSIGNED_SHORT, "luminance16"
    if _gl_has_attrs(gl_module, ("GL_R8", "GL_RED", "GL_UNSIGNED_BYTE")):
        return gl_module.GL_R8, gl_module.GL_RED, gl_module.GL_UNSIGNED_BYTE, "r8"
    return gl_module.GL_LUMINANCE, gl_module.GL_LUMINANCE, gl_module.GL_UNSIGNED_BYTE, "luminance8"


def _compute_image_format_layout(texture_format_name):
    name = str(texture_format_name or "").lower()
    if name == "r16":
        return "r16"
    if name == "r8":
        return "r8"
    return ""


def _preview_factors_for_shape(shape_zyx, max_dim):
    limit = max(1, int(max_dim))
    return tuple(max(1, int(math.ceil(int(size) / float(limit)))) for size in shape_zyx)


def _preview_shape_for_factors(shape_zyx, factors_zyx):
    return tuple(int(math.ceil(int(size) / float(max(1, int(factor))))) for size, factor in zip(shape_zyx, factors_zyx))


def _preview_shape_bytes(shape_zyx, bytes_per_voxel):
    if len(shape_zyx) != 3 or min(tuple(int(value) for value in shape_zyx)) <= 0:
        return 0
    return int(np.prod(tuple(int(value) for value in shape_zyx))) * int(max(1, bytes_per_voxel))


def _budget_limited_preview_shape(shape_zyx, requested_max_dim, bytes_per_voxel, budget_bytes, max_texture_dim):
    source_shape = tuple(int(value) for value in shape_zyx)
    requested_limit = max(1, int(requested_max_dim))
    gl_limit = int(max_texture_dim or requested_limit)
    limit = max(1, min(requested_limit, gl_limit))
    budget = int(max(0, budget_bytes or 0))
    factors = _preview_factors_for_shape(source_shape, limit)
    target_shape = _preview_shape_for_factors(source_shape, factors)
    target_bytes = _preview_shape_bytes(target_shape, bytes_per_voxel)
    degrade_reason = ""
    if budget > 0 and target_bytes > budget:
        degrade_reason = "texture_budget"
        while limit > GPU_VOLUME_STREAM_BUILD_MIN_DIM:
            limit = max(GPU_VOLUME_STREAM_BUILD_MIN_DIM, int(math.floor(limit * 0.85)))
            factors = _preview_factors_for_shape(source_shape, limit)
            target_shape = _preview_shape_for_factors(source_shape, factors)
            target_bytes = _preview_shape_bytes(target_shape, bytes_per_voxel)
            if target_bytes <= budget:
                break
        if target_bytes > budget and limit > 1:
            voxel_budget = max(1, int(budget / max(1, bytes_per_voxel)))
            scale = max(1.0, (float(np.prod(source_shape)) / float(voxel_budget)) ** (1.0 / 3.0))
            limit = max(1, min(limit, int(math.floor(max(source_shape) / scale))))
            factors = _preview_factors_for_shape(source_shape, limit)
            target_shape = _preview_shape_for_factors(source_shape, factors)
            target_bytes = _preview_shape_bytes(target_shape, bytes_per_voxel)
    return {
        "requested_max_dim": int(requested_limit),
        "target_max_dim": int(limit),
        "factors": tuple(int(value) for value in factors),
        "shape": tuple(int(value) for value in target_shape),
        "bytes": int(target_bytes),
        "degraded": bool(limit < requested_limit or bool(degrade_reason)),
        "degrade_reason": degrade_reason,
    }


def _sample_intensity_window_for_gpu_upload(array, max_samples=1_000_000):
    source = np.asarray(array)
    if source.size <= 0:
        return 0.0, 0.0
    step = max(1, int(math.ceil((float(source.size) / float(max_samples)) ** (1.0 / max(source.ndim, 1)))))
    if source.ndim == 3:
        sample = np.asarray(source[::step, ::step, ::step], dtype=np.float32).reshape(-1)
    else:
        sample = np.asarray(source.reshape(-1)[::step], dtype=np.float32)
    finite = sample[np.isfinite(sample)]
    if finite.size == 0:
        return 0.0, 0.0
    low = float(np.percentile(finite, 1.0))
    high = float(np.percentile(finite, 99.5))
    if high <= low:
        low = float(np.min(finite))
        high = float(np.max(finite))
    return low, high


def _reduceat_starts(length, factor):
    return np.arange(0, int(length), max(1, int(factor)), dtype=np.int64)


def _downsample_source_to_upload_slab(source, factors, target_shape, oz0, oz1, algorithm, preserve_source, intensity_window):
    zf, yf, xf = tuple(max(1, int(value)) for value in factors)
    z_count, y_count, x_count = tuple(int(value) for value in target_shape)
    algorithm = str(algorithm or "hybrid").lower()
    if algorithm not in {"stride", "mean", "max", "hybrid"}:
        algorithm = "hybrid"
    preserve = bool(preserve_source and np.dtype(source.dtype) == np.uint16)
    upload_dtype = np.uint16 if preserve else np.uint8
    result = np.empty((int(oz1) - int(oz0), y_count, x_count), dtype=np.float32 if not preserve else np.uint16)
    x_starts = _reduceat_starts(source.shape[2], xf)[:x_count]
    tail_count = int(source.shape[2] - int(x_starts[-1])) if len(x_starts) else 0
    tail_scale = float(xf) / float(tail_count) if tail_count > 0 and tail_count != xf else 1.0
    for out_index, oz in enumerate(range(int(oz0), int(oz1))):
        z0 = min(int(source.shape[0]), int(oz) * zf)
        z1 = min(int(source.shape[0]), z0 + zf)
        if algorithm == "stride":
            plane = np.asarray(source[z0, ::yf, ::xf])[:y_count, :x_count]
            result[out_index] = plane
            continue
        for oy, y0 in enumerate(range(0, int(source.shape[1]), yf)):
            if oy >= y_count:
                break
            y1 = min(int(source.shape[1]), y0 + yf)
            if algorithm == "max":
                block = np.asarray(source[z0:z1, y0:y1])
                row = np.maximum.reduceat(block, x_starts, axis=2).max(axis=(0, 1))
            else:
                block = np.asarray(source[z0:z1, y0:y1], dtype=np.float32)
                mean_row = np.add.reduceat(block, x_starts, axis=2).sum(axis=(0, 1)) / float((z1 - z0) * (y1 - y0) * xf)
                if tail_scale != 1.0:
                    mean_row[-1] *= tail_scale
                if algorithm == "mean":
                    row = mean_row
                else:
                    max_row = np.maximum.reduceat(block, x_starts, axis=2).max(axis=(0, 1))
                    row = mean_row * 0.65 + max_row * 0.35
            result[out_index, oy] = row[:x_count]
    if preserve:
        return np.ascontiguousarray(np.clip(np.rint(result), 0, np.iinfo(upload_dtype).max).astype(upload_dtype))
    if np.dtype(source.dtype) == np.uint8 and algorithm == "stride":
        return np.ascontiguousarray(np.clip(np.rint(result), 0, 255).astype(np.uint8))
    low, high = (float(intensity_window[0]), float(intensity_window[1]))
    if high <= low:
        return np.zeros(result.shape, dtype=np.uint8)
    scale = 255.0 / max(high - low, 1e-6)
    return np.ascontiguousarray(np.clip((result - low) * scale, 0.0, 255.0).astype(np.uint8))


def _downsample_mask_to_upload_slab(source, factors, target_shape, oz0, oz1, algorithm="occupancy"):
    zf, yf, xf = tuple(max(1, int(value)) for value in factors)
    z_count, y_count, x_count = tuple(int(value) for value in target_shape)
    algorithm = str(algorithm or "occupancy").lower()
    result = np.zeros((int(oz1) - int(oz0), y_count, x_count), dtype=np.uint8)
    for out_index, oz in enumerate(range(int(oz0), int(oz1))):
        z0 = min(int(source.shape[0]), int(oz) * zf)
        z1 = min(int(source.shape[0]), z0 + zf)
        if algorithm == "nearest":
            plane = np.asarray(source[z0, ::yf, ::xf])[:y_count, :x_count]
            result[out_index] = np.where(plane > 0, 255, 0).astype(np.uint8, copy=False)
            continue
        for oy, y0 in enumerate(range(0, int(source.shape[1]), yf)):
            if oy >= y_count:
                break
            y1 = min(int(source.shape[1]), y0 + yf)
            for ox, x0 in enumerate(range(0, int(source.shape[2]), xf)):
                if ox >= x_count:
                    break
                x1 = min(int(source.shape[2]), x0 + xf)
                if np.any(np.asarray(source[z0:z1, y0:y1, x0:x1]) > 0):
                    result[out_index, oy, ox] = 255
    return np.ascontiguousarray(result)


def probe_gpu_preview_build_capabilities(gl_module=None):
    gl_module = gl_module or GL
    if gl_module is None:
        return GpuPreviewBuildCapabilities(reason=f"PyOpenGL is unavailable: {_PYOPENGL_IMPORT_ERROR}")
    try:
        vendor = _decode_gl_string(gl_module.glGetString(gl_module.GL_VENDOR))
        renderer = _decode_gl_string(gl_module.glGetString(gl_module.GL_RENDERER))
        version = _decode_gl_string(gl_module.glGetString(gl_module.GL_VERSION))
    except Exception as exc:
        return GpuPreviewBuildCapabilities(reason=f"OpenGL capability probe failed: {exc}")
    if not version:
        return GpuPreviewBuildCapabilities(reason="OpenGL capability probe needs a current context")
    major, minor, is_es = _parse_gl_version(version)
    extensions = _gl_extensions(gl_module)
    max_3d = _gl_integer(gl_module, getattr(gl_module, "GL_MAX_3D_TEXTURE_SIZE", 0), 0)
    compute_count = _gl_integer_tuple(gl_module, getattr(gl_module, "GL_MAX_COMPUTE_WORK_GROUP_COUNT", 0), 3)
    compute_size = _gl_integer_tuple(gl_module, getattr(gl_module, "GL_MAX_COMPUTE_WORK_GROUP_SIZE", 0), 3)
    supports_compute = (
        (major, minor) >= (4, 3)
        or (is_es and (major, minor) >= (3, 1))
        or _gl_has_extension(extensions, "GL_ARB_compute_shader")
    ) and hasattr(gl_module, "glDispatchCompute")
    supports_image = (
        (major, minor) >= (4, 2)
        or _gl_has_extension(extensions, "GL_ARB_shader_image_load_store")
    )
    supports_r16 = all(hasattr(gl_module, name) for name in ("GL_R16", "GL_RED", "GL_UNSIGNED_SHORT"))
    supports_fence = (
        (major, minor) >= (3, 2)
        or _gl_has_extension(extensions, "GL_ARB_sync")
    ) and hasattr(gl_module, "glFenceSync")
    if max_3d <= 0:
        backend = GPU_PREVIEW_BUILD_BACKEND_UNAVAILABLE
        reason = "3D texture support was not reported by the current OpenGL context"
        available = False
    elif supports_compute and supports_image and supports_r16:
        backend = GPU_PREVIEW_BUILD_BACKEND_COMPUTE
        reason = ""
        available = True
    else:
        backend = GPU_PREVIEW_BUILD_BACKEND_FRAGMENT
        reason = "Compute preview build is unavailable; fragment fallback may be used"
        available = True
    return GpuPreviewBuildCapabilities(
        available=available,
        backend=backend,
        reason=reason,
        vendor=vendor,
        renderer=renderer,
        version=version,
        max_3d_texture_size=max_3d,
        max_compute_work_group_count=compute_count,
        max_compute_work_group_size=compute_size,
        supports_compute_shader=supports_compute,
        supports_image_load_store=supports_image,
        supports_r16_texture=supports_r16,
        supports_fence_sync=supports_fence,
    )


def _compact_renderer_text(value):
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    if "RTX 3090" in text:
        return "RTX 3090"
    if "NVIDIA" in text and "GeForce" in text:
        return text.replace("NVIDIA GeForce ", "NVIDIA ")
    if len(text) > 42:
        return text[:39].rstrip() + "..."
    return text


def _coerce_rgb(rgb, fallback=(1.0, 0.83, 0.30)):
    try:
        values = tuple(float(value) for value in rgb)
    except (TypeError, ValueError):
        values = tuple(float(value) for value in fallback)
    if len(values) != 3:
        values = tuple(float(value) for value in fallback)
    return tuple(max(0.0, min(1.0, value)) for value in values)


def _crisp_sampling_enabled(clarity_mode, render_mode, clip_plane_enabled=False):
    return False


def _texture_filter_name(clarity_mode, render_mode, clip_plane_enabled=False):
    return "nearest" if _crisp_sampling_enabled(clarity_mode, render_mode, clip_plane_enabled) else "linear"


def _display_scaling_name(clarity_mode, render_mode, clip_plane_enabled=False):
    return "nearest" if _crisp_sampling_enabled(clarity_mode, render_mode, clip_plane_enabled) else "smooth"


def volume_pan_limit_for_zoom(zoom):
    zoom = max(1.0, float(zoom))
    return max(8.0, min(64.0, 4.0 + zoom * 2.0))


def build_volume_transfer_lut(
    preset="amber",
    tint_rgb=(1.0, 0.83, 0.30),
    cutoff=0.0,
    opacity=1.0,
    clarity=False,
    size=GPU_VOLUME_TRANSFER_LUT_SIZE,
):
    """Build TaxaMask's RGBA transfer function LUT for read-only volume display."""
    return build_transfer_lut(
        preset=preset,
        tint_rgb=tint_rgb,
        cutoff=cutoff,
        opacity=opacity,
        clarity=clarity,
        size=size,
    )


def _coerce_unit_float(value, fallback=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(fallback)
    if not math.isfinite(number):
        number = float(fallback)
    return max(0.0, min(1.0, number))


def _coerce_gradient_range(value, fallback=(0.04, 0.34)):
    try:
        values = tuple(float(item) for item in value)
    except (TypeError, ValueError):
        values = tuple(float(item) for item in fallback)
    if len(values) != 2 or not all(math.isfinite(item) for item in values):
        values = tuple(float(item) for item in fallback)
    low = max(0.0, min(0.999, float(values[0])))
    high = max(low + 0.001, min(1.0, float(values[1])))
    return (low, high)


def _shader_quality_mode(value):
    mode = str(value or "preset").lower()
    if mode in {"off", "preset", "all_still"}:
        return mode
    return "preset"


def _shader_quality_enabled_for_preset(preset, quality_mode="preset"):
    quality_mode = _shader_quality_mode(quality_mode)
    if quality_mode == "off":
        return False
    if quality_mode == "all_still":
        return True
    return str(preset or "").lower() in {"morphology", "publication"}


def _gradient_opacity_settings(preset, render_mode, quality_mode="all_still"):
    if not _shader_quality_enabled_for_preset(preset, quality_mode):
        return 0.0, (0.04, 0.34)
    if str(render_mode) != "still":
        return 0.0, (0.04, 0.34)
    transfer = normalize_transfer_function(None, preset=preset)
    gradient = transfer.get("gradient_opacity") if isinstance(transfer, dict) else {}
    if not bool(gradient.get("enabled", False)):
        return 0.0, (0.04, 0.34)
    low, high = _coerce_gradient_range((gradient.get("low", 0.04), gradient.get("high", 0.34)))
    strength = _coerce_unit_float(gradient.get("strength", 0.0), 0.0)
    return strength, (low, high)


def _jitter_strength_for_render(render_mode, projection_mode, gradient_opacity=0.0):
    if str(render_mode) != "still" or str(projection_mode or "").lower() != "composite":
        return 0.0
    return 0.42 if float(gradient_opacity) > 0.0 else 0.28


def _adaptive_step_strength_for_render(render_mode, projection_mode, mask_mode="image_only", clip_plane_enabled=False):
    if str(render_mode) != "still":
        return 0.0
    if str(projection_mode or "").lower() != "composite":
        return 0.0
    if str(mask_mode or "").lower() != "image_only":
        return 0.0
    if bool(clip_plane_enabled):
        return 0.0
    return 0.35


def volume_shader_quality_settings(
    preset="amber",
    render_mode="still",
    projection_mode="composite",
    mask_mode="image_only",
    clip_plane_enabled=False,
    quality_mode="preset",
):
    """Return display-only shader quality controls derived from the transfer preset."""
    quality_mode = _shader_quality_mode(quality_mode)
    enabled = _shader_quality_enabled_for_preset(preset, quality_mode)
    gradient_opacity, gradient_range = _gradient_opacity_settings(preset, render_mode, quality_mode)
    return {
        "shader_quality_mode": quality_mode,
        "jitter_strength": _jitter_strength_for_render(render_mode, projection_mode, gradient_opacity) if enabled else 0.0,
        "adaptive_step_strength": _adaptive_step_strength_for_render(render_mode, projection_mode, mask_mode, clip_plane_enabled) if enabled else 0.0,
        "gradient_opacity": gradient_opacity,
        "gradient_opacity_range": gradient_range,
    }


def volume_shape_scale(shape_zyx, spacing_zyx=None):
    """Return normalized x/y/z display scale from source volume geometry."""
    try:
        shape = [float(value) for value in tuple(shape_zyx or ())]
    except (TypeError, ValueError):
        shape = []
    if len(shape) != 3 or min(shape) <= 0:
        return (1.0, 1.0, 1.0)
    spacing = None
    try:
        spacing_values = [float(value) for value in tuple(spacing_zyx or ())]
    except (TypeError, ValueError):
        spacing_values = []
    if len(spacing_values) == 3 and min(spacing_values) > 0:
        spacing = spacing_values
    physical_zyx = [shape[index] * (spacing[index] if spacing else 1.0) for index in range(3)]
    max_dim = max(max(physical_zyx), 1.0)
    z_scale = max(physical_zyx[0] / max_dim, 0.08)
    y_scale = physical_zyx[1] / max_dim
    x_scale = physical_zyx[2] / max_dim
    return (float(x_scale), float(y_scale), float(z_scale))


def _compile_shader(source, shader_type):
    shader = GL.glCreateShader(shader_type)
    GL.glShaderSource(shader, source)
    GL.glCompileShader(shader)
    if not GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS):
        log = _shader_log(shader)
        GL.glDeleteShader(shader)
        raise RuntimeError(log or "OpenGL shader compile failed")
    return shader


def _link_program(vertex_source, fragment_source):
    vertex = _compile_shader(vertex_source, GL.GL_VERTEX_SHADER)
    fragment = _compile_shader(fragment_source, GL.GL_FRAGMENT_SHADER)
    program = GL.glCreateProgram()
    GL.glAttachShader(program, vertex)
    GL.glAttachShader(program, fragment)
    GL.glLinkProgram(program)
    GL.glDeleteShader(vertex)
    GL.glDeleteShader(fragment)
    if not GL.glGetProgramiv(program, GL.GL_LINK_STATUS):
        log = _program_log(program)
        GL.glDeleteProgram(program)
        raise RuntimeError(log or "OpenGL shader link failed")
    return program


def _link_compute_program(compute_source):
    if not hasattr(GL, "GL_COMPUTE_SHADER"):
        raise RuntimeError("OpenGL compute shader enum is unavailable")
    compute = _compile_shader(compute_source, GL.GL_COMPUTE_SHADER)
    program = GL.glCreateProgram()
    GL.glAttachShader(program, compute)
    GL.glLinkProgram(program)
    GL.glDeleteShader(compute)
    if not GL.glGetProgramiv(program, GL.GL_LINK_STATUS):
        log = _program_log(program)
        GL.glDeleteProgram(program)
        raise RuntimeError(log or "OpenGL compute shader link failed")
    return program


def _rotation_inverse_matrix(yaw_degrees, pitch_degrees):
    yaw = math.radians(float(yaw_degrees))
    pitch = math.radians(float(pitch_degrees))
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    rot_yaw = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=np.float32)
    rot_pitch = np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]], dtype=np.float32)
    rotation = rot_yaw @ rot_pitch
    return np.ascontiguousarray(rotation.T, dtype=np.float32)


def camera_distance_for_inside_zoom(shape_scale, inv_rotation, zoom, inside_depth):
    """Return a camera distance that can enter the volume without crossing out the back side."""
    scale = np.asarray(shape_scale or (1.0, 1.0, 1.0), dtype=np.float32).reshape(-1)
    if scale.size != 3 or not np.all(np.isfinite(scale)) or float(np.min(scale)) <= 0.0:
        scale = np.asarray((1.0, 1.0, 1.0), dtype=np.float32)
    matrix = np.asarray(inv_rotation, dtype=np.float32).reshape((3, 3))
    view_dir = matrix @ np.asarray((0.0, 0.0, -1.0), dtype=np.float32)
    abs_dir = np.abs(view_dir)
    half_size = np.maximum(scale * 0.5, 0.001)
    valid = abs_dir > 1e-5
    center_to_surface = float(np.min(half_size[valid] / abs_dir[valid])) if np.any(valid) else 0.5
    outside_distance = 1.45
    inside = max(0.0, min(1.6, float(inside_depth)))
    if inside <= 1.0:
        return max(0.0, outside_distance * (1.0 - inside))
    back_fraction = min(0.75, ((inside - 1.0) / 0.6) * 0.75)
    return -center_to_surface * back_fraction


def front_clip_start_t(near_hit, far_hit, front_clip):
    """Return the ray start after discarding the viewer-side segment."""
    ray_start = max(float(near_hit), 0.0)
    ray_end = float(far_hit)
    clip = max(0.0, min(0.92, float(front_clip)))
    return ray_start + (ray_end - ray_start) * clip


class _GpuVolumeRenderCore:
    """Shared OpenGL state for embedded and offscreen TIF volume previews."""

    def _init_render_state(self):
        self.current_theme = "dark"
        self._clear_color_rgba = (*GPU_VOLUME_DARK_CLEAR_RGB, 1.0)
        self._volume_data = None
        self._volume_shape = ()
        self._volume_cache_key = None
        self._source_shape = ()
        self._source_spacing = ()
        self._upload_needed = False
        self._initialized = False
        self._failed = False
        self._failure_reason = ""
        self._program = None
        self._quad_vbo = None
        self._texture_id = None
        self._mask_texture_id = None
        self._mask_data = None
        self._mask_shape = ()
        self._mask_cache_key = None
        self._mask_upload_needed = False
        self._texture_cache = OrderedDict()
        self._texture_cache_bytes = 0
        self._texture_cache_hits = 0
        self._texture_cache_misses = 0
        self._texture_cache_budget_bytes = _gpu_texture_cache_budget_bytes()
        self._stream_build_yield_callback = None
        self._preview_build_capabilities = GpuPreviewBuildCapabilities(reason="GPU preview build capability has not been probed")
        self._preview_texture_provider = None
        self._preview_stream_build_stats = {}
        self._transfer_lut_texture_id = None
        self._transfer_lut_data = build_volume_transfer_lut()
        self._transfer_lut_upload_needed = True
        self._cutoff = 0.35
        self._yaw = -35.0
        self._pitch = 20.0
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._clarity_mode = False
        self._render_quality = 384
        self._sample_steps = 768
        self._inside_depth = 0.0
        self._front_clip = 0.0
        self._projection_mode = "composite"
        self._mask_mode = "image_only"
        self._mask_opacity = 0.45
        self._enhancement = 0.0
        self._tone_gamma = 1.0
        self._jitter_strength = 0.0
        self._adaptive_step_strength = 0.0
        self._gradient_opacity = 0.0
        self._gradient_opacity_range = (0.04, 0.34)
        self._surface_refine = False
        self._clip_plane_enabled = False
        self._clip_plane_depth = 0.0
        self._clip_plane_normal = (0.0, 0.0, 1.0)
        self._fast_interaction = False
        self._supersample_scale = 1.0
        self._tint_rgb = (1.0, 0.83, 0.30)
        self._renderer_label = ""
        self._renderer_details = ""
        self._uploaded_shape = ()
        self._uploaded_bytes = 0
        self._last_upload_ms = 0.0
        self._last_draw_ms = 0.0
        self._last_steps = 0
        self._render_mode = "still"
        self._uploaded_dtype = ""
        self._transfer_preset = "amber"
        self._transfer_opacity = 1.0

    def set_theme(self, theme):
        self.current_theme = normalize_theme(theme)
        rgb = GPU_VOLUME_LIGHT_CLEAR_RGB if self.current_theme == "light" else GPU_VOLUME_DARK_CLEAR_RGB
        self._clear_color_rgba = (float(rgb[0]), float(rgb[1]), float(rgb[2]), 1.0)

    def _apply_clear_color(self):
        red, green, blue, alpha = getattr(self, "_clear_color_rgba", (*GPU_VOLUME_DARK_CLEAR_RGB, 1.0))
        GL.glClearColor(float(red), float(green), float(blue), float(alpha))

    def set_stream_build_yield_callback(self, callback):
        self._stream_build_yield_callback = callback if callable(callback) else None

    def _yield_stream_build_events(self):
        callback = getattr(self, "_stream_build_yield_callback", None)
        if not callable(callback):
            return
        try:
            callback()
        except Exception:
            pass

    def _store_volume_data(self, volume, source_shape=None, spacing_zyx=None, cache_key=None):
        if volume is None:
            self.clear_volume()
            return False
        if cache_key is not None and self._activate_cached_texture(cache_key, "volume"):
            self._volume_cache_key = cache_key
            self._source_shape = tuple(int(value) for value in (source_shape or self._volume_shape))
            try:
                next_spacing = tuple(float(value) for value in (spacing_zyx or ()))
            except (TypeError, ValueError):
                next_spacing = ()
            self._source_spacing = next_spacing if len(next_spacing) == 3 and min(next_spacing) > 0 else ()
            self._volume_data = np.asarray(volume)
            self._upload_needed = False
            self._set_preview_texture_provider(
                gpu_texture_preview_provider(
                    self._texture_id,
                    self._volume_shape,
                    self._uploaded_dtype,
                    source_shape=self._source_shape,
                    spacing_zyx=self._source_spacing,
                    cache_key=cache_key,
                    build_backend="gpu_cache",
                )
            )
            return True
        source = np.asarray(volume)
        if source.dtype == np.uint16:
            array = np.ascontiguousarray(source, dtype=np.uint16)
        else:
            array = np.ascontiguousarray(source, dtype=np.uint8)
        if array.ndim != 3 or min(array.shape) <= 0:
            self.clear_volume()
            return False
        next_source_shape = tuple(int(value) for value in (source_shape or array.shape))
        if len(next_source_shape) != 3 or min(next_source_shape) <= 0:
            next_source_shape = tuple(int(value) for value in array.shape)
        try:
            next_spacing = tuple(float(value) for value in (spacing_zyx or ()))
        except (TypeError, ValueError):
            next_spacing = ()
        if len(next_spacing) != 3 or min(next_spacing) <= 0:
            next_spacing = ()
        if self._volume_data is not array:
            self._volume_data = array
            self._volume_shape = tuple(int(value) for value in array.shape)
            self._volume_cache_key = cache_key
            self._upload_needed = True
        else:
            self._volume_cache_key = cache_key
        self._source_shape = next_source_shape
        self._source_spacing = next_spacing
        self._set_preview_texture_provider(
            cpu_volume_preview_provider(
                array,
                source_shape=next_source_shape,
                spacing_zyx=next_spacing,
                cache_key=cache_key,
                build_backend="cpu",
            )
        )
        return True

    def _set_preview_texture_provider(self, provider):
        self._preview_texture_provider = provider

    def _preview_provider_stats(self):
        provider = getattr(self, "_preview_texture_provider", None)
        if provider is None:
            return {}
        if hasattr(provider, "to_stats"):
            return provider.to_stats()
        return {"kind": str(getattr(provider, "kind", "") or type(provider).__name__)}

    def _store_mask_data(self, mask, cache_key=None):
        if mask is None:
            if self._mask_data is not None or self._mask_texture_id:
                self._detach_mask_texture()
            self._mask_data = None
            self._mask_shape = ()
            self._mask_cache_key = None
            self._mask_upload_needed = False
            return False
        if cache_key is not None and self._activate_cached_texture(cache_key, "mask"):
            self._mask_cache_key = cache_key
            self._mask_data = np.asarray(mask)
            self._mask_upload_needed = False
            return True
        source = np.asarray(mask)
        if source.ndim != 3 or min(source.shape) <= 0:
            self._detach_mask_texture()
            self._mask_data = None
            self._mask_shape = ()
            self._mask_cache_key = None
            self._mask_upload_needed = False
            return False
        array = np.ascontiguousarray((source > 0).astype(np.uint8) * 255)
        if self._mask_data is None or self._mask_data.shape != array.shape or not np.array_equal(self._mask_data, array):
            self._mask_data = array
            self._mask_shape = tuple(int(value) for value in array.shape)
            self._mask_cache_key = cache_key
            self._mask_upload_needed = True
        else:
            self._mask_cache_key = cache_key
        return True

    def _can_stream_build_volume_texture(self):
        capabilities = getattr(self, "_preview_build_capabilities", None)
        if capabilities is None:
            capabilities = probe_gpu_preview_build_capabilities()
            self._preview_build_capabilities = capabilities
        return bool(capabilities.available and int(capabilities.max_3d_texture_size or 0) > 0)

    def _can_compute_build_volume_texture(self):
        capabilities = getattr(self, "_preview_build_capabilities", None)
        if capabilities is None:
            capabilities = probe_gpu_preview_build_capabilities()
            self._preview_build_capabilities = capabilities
        return bool(
            capabilities.available
            and capabilities.backend == GPU_PREVIEW_BUILD_BACKEND_COMPUTE
            and capabilities.supports_compute_shader
            and capabilities.supports_image_load_store
            and int(capabilities.max_3d_texture_size or 0) > 0
        )

    def _try_compute_upload_source_volume_texture(
        self,
        source,
        max_dim,
        algorithm,
        preserve_source,
        cache_key,
        source_shape,
        spacing,
        target_plan,
        upload_dtype,
        upload_dtype_text,
        texture_format_name,
        internal_format,
        upload_format,
        pixel_type,
        bytes_per_voxel,
        effective_budget,
        staging_budget_bytes,
    ):
        if not self._can_compute_build_volume_texture():
            return None
        algorithm_name = str(algorithm or "hybrid").lower()
        if algorithm_name not in {"stride", "mean", "max", "hybrid"}:
            algorithm_name = "hybrid"
        if np.dtype(source.dtype) not in (np.dtype(np.uint8), np.dtype(np.uint16)):
            return None
        source_internal_format, source_upload_format, source_pixel_type, source_texture_format_name = _volume_texture_format(source.dtype)
        image_layout = _compute_image_format_layout(texture_format_name)
        if not image_layout:
            return None
        if not all(hasattr(GL, name) for name in ("glBindImageTexture", "glDispatchCompute", "glMemoryBarrier")):
            return None
        if not hasattr(GL, "GL_SHADER_IMAGE_ACCESS_BARRIER_BIT"):
            return None
        target_shape = tuple(int(value) for value in target_plan["shape"])
        z_count, y_count, x_count = target_shape
        zf, yf, xf = tuple(max(1, int(value)) for value in target_plan.get("factors") or (1, 1, 1))
        algorithm_ids = {"stride": 0, "mean": 1, "max": 2, "hybrid": 3}
        algorithm_id = int(algorithm_ids[algorithm_name])
        source_dtype = np.dtype(source.dtype)
        source_dtype_max = float(np.iinfo(source_dtype).max) if np.issubdtype(source_dtype, np.integer) else 1.0
        max_texture_dim = int(getattr(self._preview_build_capabilities, "max_3d_texture_size", 0) or 0)
        if max_texture_dim > 0 and (int(source.shape[2]) > max_texture_dim or int(source.shape[1]) > max_texture_dim):
            return None
        source_texture_id = None
        program = None
        texture_id = None
        old_texture_id = self._texture_id
        started = time.perf_counter()
        try:
            protect_active = int(target_plan["bytes"]) + int(self._texture_cache_bytes) <= int(max(0, self._texture_cache_budget_bytes))
            released_for_budget = self._reserve_texture_cache_bytes(
                int(target_plan["bytes"]),
                protected_ids={old_texture_id} if protect_active else set(),
                protect_active=protect_active,
            )
            texture_id = self._new_upload_texture_id("volume")
            GL.glBindTexture(GL.GL_TEXTURE_3D, texture_id)
            texture_filter = GL.GL_NEAREST if bool(preserve_source) else GL.GL_LINEAR
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MIN_FILTER, texture_filter)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MAG_FILTER, texture_filter)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_R, GL.GL_CLAMP_TO_EDGE)
            GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
            GL.glTexImage3D(
                GL.GL_TEXTURE_3D,
                0,
                internal_format,
                int(x_count),
                int(y_count),
                int(z_count),
                0,
                upload_format,
                pixel_type,
                None,
            )
            source_texture_id = GL.glGenTextures(1)
            GL.glBindTexture(GL.GL_TEXTURE_3D, source_texture_id)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_R, GL.GL_CLAMP_TO_EDGE)
            plane_bytes = max(1, int(source.shape[1]) * int(source.shape[2]) * int(source_dtype.itemsize))
            source_planes_per_target_chunk = 1 if algorithm_name == "stride" else max(1, int(zf))
            z_chunk = max(1, min(int(z_count), int(max(1, staging_budget_bytes) / max(1, plane_bytes * source_planes_per_target_chunk))))
            shader_source = _COMPUTE_COPY_SHADER_TEMPLATE.replace("__IMAGE_FORMAT__", image_layout)
            program = _link_compute_program(shader_source)
            GL.glUseProgram(program)
            source_uniform = GL.glGetUniformLocation(program, "u_source")
            source_shape_uniform = GL.glGetUniformLocation(program, "u_source_shape")
            target_slab_shape_uniform = GL.glGetUniformLocation(program, "u_target_slab_shape")
            factors_uniform = GL.glGetUniformLocation(program, "u_factors")
            algorithm_uniform = GL.glGetUniformLocation(program, "u_algorithm")
            apply_window_uniform = GL.glGetUniformLocation(program, "u_apply_window")
            window_uniform = GL.glGetUniformLocation(program, "u_window")
            z_offset_uniform = GL.glGetUniformLocation(program, "u_z_offset")
            if source_uniform >= 0:
                GL.glUniform1i(source_uniform, 0)
            if factors_uniform >= 0:
                GL.glUniform3i(factors_uniform, int(xf), int(yf), 1 if algorithm_name == "stride" else int(zf))
            if algorithm_uniform >= 0:
                GL.glUniform1i(algorithm_uniform, int(algorithm_id))
            apply_window = bool(
                np.dtype(upload_dtype) == np.uint8
                and (source_dtype != np.uint8 or algorithm_name != "stride")
            )
            if apply_window_uniform >= 0:
                GL.glUniform1i(apply_window_uniform, 1 if apply_window else 0)
            if window_uniform >= 0:
                if apply_window:
                    low, high = _sample_intensity_window_for_gpu_upload(source)
                    scale = max(float(source_dtype_max), 1.0)
                    GL.glUniform2f(window_uniform, float(low) / scale, float(high) / scale)
                else:
                    GL.glUniform2f(window_uniform, 0.0, 1.0)
            GL.glBindImageTexture(0, texture_id, 0, True, 0, GL.GL_WRITE_ONLY, internal_format)
            local_x, local_y, local_z = GPU_VOLUME_COMPUTE_LOCAL_SIZE
            for oz0 in range(0, int(z_count), int(z_chunk)):
                oz1 = min(int(z_count), oz0 + int(z_chunk))
                source_z0 = min(int(source.shape[0]), int(oz0) * int(zf))
                source_z1 = min(
                    int(source.shape[0]),
                    max(
                        source_z0 + 1,
                        (int(oz1) - 1) * int(zf) + (1 if algorithm_name == "stride" else int(zf)),
                    ),
                )
                if algorithm_name == "stride":
                    slab = np.ascontiguousarray(source[source_z0:source_z1:int(zf)])
                else:
                    slab = np.ascontiguousarray(source[source_z0:source_z1])
                GL.glActiveTexture(GL.GL_TEXTURE0)
                GL.glBindTexture(GL.GL_TEXTURE_3D, source_texture_id)
                GL.glTexImage3D(
                    GL.GL_TEXTURE_3D,
                    0,
                    source_internal_format,
                    int(source.shape[2]),
                    int(source.shape[1]),
                    int(slab.shape[0]),
                    0,
                    source_upload_format,
                    source_pixel_type,
                    slab,
                )
                if source_shape_uniform >= 0:
                    GL.glUniform3i(source_shape_uniform, int(source.shape[2]), int(source.shape[1]), int(slab.shape[0]))
                if target_slab_shape_uniform >= 0:
                    GL.glUniform3i(target_slab_shape_uniform, int(x_count), int(y_count), int(oz1 - oz0))
                if z_offset_uniform >= 0:
                    GL.glUniform1i(z_offset_uniform, int(oz0))
                GL.glDispatchCompute(
                    int(math.ceil(float(x_count) / float(local_x))),
                    int(math.ceil(float(y_count) / float(local_y))),
                    int(math.ceil(float(oz1 - oz0) / float(local_z))),
                )
                GL.glMemoryBarrier(GL.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT)
                self._yield_stream_build_events()
            self._texture_id = texture_id
            self._volume_data = None
            self._volume_shape = target_shape
            self._volume_cache_key = cache_key
            self._source_shape = source_shape
            self._source_spacing = spacing
            self._upload_needed = False
            self._uploaded_shape = self._volume_shape
            self._uploaded_bytes = int(np.prod(self._volume_shape)) * int(bytes_per_voxel)
            self._uploaded_dtype = upload_dtype_text
            self._last_upload_ms = (time.perf_counter() - started) * 1000.0
            self._preview_stream_build_stats = {
                "backend": "gpu_compute",
                "algorithm": str(algorithm_name),
                "preserve_source": bool(preserve_source),
                "requested_max_dim": int(target_plan["requested_max_dim"]),
                "actual_max_dim": int(max(self._volume_shape) if self._volume_shape else 0),
                "target_max_dim": int(target_plan["target_max_dim"]),
                "source_shape_zyx": tuple(int(value) for value in source_shape),
                "shape_zyx": tuple(int(value) for value in self._volume_shape),
                "factors_zyx": tuple(int(value) for value in target_plan["factors"]),
                "bytes": int(self._uploaded_bytes),
                "budget_bytes": int(max(0, self._texture_cache_budget_bytes)),
                "effective_budget_bytes": int(max(0, effective_budget)),
                "staging_budget_bytes": int(max(1, staging_budget_bytes)),
                "staging_chunk_depth": int(z_chunk),
                "source_staging_chunk_depth": int(max(1, z_chunk * source_planes_per_target_chunk)),
                "texture_format": str(texture_format_name),
                "source_texture_format": str(source_texture_format_name),
                "degraded": bool(target_plan["degraded"]),
                "degrade_reason": str(target_plan["degrade_reason"]),
                "released_active_for_budget": bool(int(old_texture_id or 0) in released_for_budget),
            }
            self._set_preview_texture_provider(
                gpu_texture_preview_provider(
                    self._texture_id,
                    self._volume_shape,
                    self._uploaded_dtype,
                    source_shape=self._source_shape,
                    spacing_zyx=self._source_spacing,
                    cache_key=cache_key,
                    build_backend="gpu_compute",
                )
            )
            self._remember_texture(
                cache_key,
                "volume",
                self._texture_id,
                self._uploaded_shape,
                self._uploaded_dtype,
                self._uploaded_bytes,
            )
            if old_texture_id and old_texture_id != texture_id and not self._texture_id_is_cached(old_texture_id) and int(old_texture_id) not in released_for_budget:
                try:
                    GL.glDeleteTextures([int(old_texture_id)])
                except Exception:
                    pass
            return self._preview_texture_provider
        except Exception as exc:
            self._preview_stream_build_stats = {
                "backend": "gpu_compute",
                "failed": True,
                "fallback": "gpu_stream",
                "error": str(exc),
            }
            if texture_id:
                try:
                    GL.glDeleteTextures([int(texture_id)])
                except Exception:
                    pass
            return None
        finally:
            if program:
                try:
                    GL.glUseProgram(0)
                    GL.glDeleteProgram(program)
                except Exception:
                    pass
            if source_texture_id:
                try:
                    GL.glDeleteTextures([int(source_texture_id)])
                except Exception:
                    pass
            try:
                GL.glBindTexture(GL.GL_TEXTURE_3D, 0)
                GL.glActiveTexture(GL.GL_TEXTURE0)
            except Exception:
                pass

    def _stream_upload_source_volume_texture(
        self,
        volume,
        max_dim,
        algorithm="hybrid",
        preserve_source=False,
        cache_key=None,
        source_shape=None,
        spacing_zyx=None,
        staging_budget_bytes=GPU_VOLUME_STREAM_BUILD_DEFAULT_STAGING_BYTES,
    ):
        source = np.asarray(volume)
        if source.ndim != 3 or min(source.shape) <= 0:
            raise ValueError(f"volume_must_be_non_empty_zyx:{getattr(source, 'shape', ())}")
        if not self._can_stream_build_volume_texture():
            raise RuntimeError(getattr(self._preview_build_capabilities, "reason", "") or "GPU preview build is unavailable")
        source_shape = tuple(int(value) for value in (source_shape or source.shape))
        if len(source_shape) != 3 or min(source_shape) <= 0:
            source_shape = tuple(int(value) for value in source.shape)
        try:
            spacing = tuple(float(value) for value in (spacing_zyx or ()))
        except (TypeError, ValueError):
            spacing = ()
        if len(spacing) != 3 or min(spacing) <= 0:
            spacing = ()
        if cache_key is not None and self._activate_cached_texture(cache_key, "volume"):
            self._volume_cache_key = cache_key
            self._source_shape = source_shape
            self._source_spacing = spacing
            self._volume_data = None
            self._set_preview_texture_provider(
                gpu_texture_preview_provider(
                    self._texture_id,
                    self._volume_shape,
                    self._uploaded_dtype,
                    source_shape=self._source_shape,
                    spacing_zyx=self._source_spacing,
                    cache_key=cache_key,
                    build_backend="gpu_cache",
                )
            )
            self._preview_stream_build_stats = {
                "backend": "gpu_cache",
                "cache_hit": True,
                "algorithm": str(algorithm or "hybrid"),
                "preserve_source": bool(preserve_source and np.dtype(source.dtype) == np.uint16),
                "requested_max_dim": int(max_dim),
                "actual_max_dim": int(max(self._volume_shape) if self._volume_shape else 0),
                "source_shape_zyx": tuple(int(value) for value in source_shape),
                "shape_zyx": tuple(int(value) for value in self._volume_shape),
                "bytes": int(self._uploaded_bytes),
                "budget_bytes": int(max(0, self._texture_cache_budget_bytes)),
                "degraded": False,
                "degrade_reason": "",
            }
            return self._preview_texture_provider
        target_limit = min(int(max_dim), int(getattr(self._preview_build_capabilities, "max_3d_texture_size", 0) or max_dim))
        preserve = bool(preserve_source and np.dtype(source.dtype) == np.uint16)
        upload_dtype = np.uint16 if preserve else np.uint8
        upload_dtype_text = "uint16" if preserve else "uint8"
        bytes_per_voxel = int(np.dtype(upload_dtype).itemsize)
        full_budget = int(max(0, self._texture_cache_budget_bytes))
        effective_budget = self._stream_build_texture_budget_bytes(cache_key=cache_key)
        target_plan = _budget_limited_preview_shape(
            source.shape,
            max(1, target_limit),
            bytes_per_voxel,
            effective_budget,
            int(getattr(self._preview_build_capabilities, "max_3d_texture_size", 0) or target_limit),
        )
        active_bytes = self._active_volume_texture_cache_bytes(exclude_key=cache_key)
        release_active_for_quality = False
        if active_bytes > 0 and full_budget > 0 and effective_budget < full_budget:
            full_budget_plan = _budget_limited_preview_shape(
                source.shape,
                max(1, target_limit),
                bytes_per_voxel,
                full_budget,
                int(getattr(self._preview_build_capabilities, "max_3d_texture_size", 0) or target_limit),
            )
            if (
                int(full_budget_plan.get("bytes") or 0) <= full_budget
                and int(full_budget_plan.get("target_max_dim") or 0) > int(target_plan.get("target_max_dim") or 0)
            ):
                target_plan = full_budget_plan
                effective_budget = full_budget
                release_active_for_quality = True
        factors = target_plan["factors"]
        target_shape = target_plan["shape"]
        if len(target_shape) != 3 or min(target_shape) <= 0:
            raise RuntimeError(f"invalid_gpu_preview_shape:{target_shape}")
        z_count, y_count, x_count = target_shape
        if z_count > int(getattr(self._preview_build_capabilities, "max_3d_texture_size", 0) or z_count):
            raise RuntimeError(f"gpu_preview_exceeds_3d_texture_limit:{target_shape}")
        internal_format, upload_format, pixel_type, texture_format_name = _volume_texture_format(upload_dtype)
        compute_provider = self._try_compute_upload_source_volume_texture(
            source,
            max_dim,
            algorithm,
            preserve,
            cache_key,
            source_shape,
            spacing,
            target_plan,
            upload_dtype,
            upload_dtype_text,
            texture_format_name,
            internal_format,
            upload_format,
            pixel_type,
            bytes_per_voxel,
            effective_budget,
            staging_budget_bytes,
        )
        if compute_provider is not None:
            return compute_provider
        old_texture_id = self._texture_id
        protect_active = (
            not release_active_for_quality
            and int(target_plan["bytes"]) + int(self._texture_cache_bytes) <= int(max(0, self._texture_cache_budget_bytes))
        )
        released_for_budget = self._reserve_texture_cache_bytes(
            int(target_plan["bytes"]),
            protected_ids={old_texture_id} if protect_active else set(),
            protect_active=protect_active,
        )
        texture_id = self._new_upload_texture_id("volume")
        GL.glBindTexture(GL.GL_TEXTURE_3D, texture_id)
        texture_filter = GL.GL_NEAREST if preserve else GL.GL_LINEAR
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MIN_FILTER, texture_filter)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MAG_FILTER, texture_filter)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_R, GL.GL_CLAMP_TO_EDGE)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        GL.glTexImage3D(
            GL.GL_TEXTURE_3D,
            0,
            internal_format,
            int(x_count),
            int(y_count),
            int(z_count),
            0,
            upload_format,
            pixel_type,
            None,
        )
        intensity_window = (0.0, 65535.0) if preserve else _sample_intensity_window_for_gpu_upload(source)
        plane_bytes = max(1, int(y_count) * int(x_count) * bytes_per_voxel)
        z_chunk = max(1, min(int(z_count), int(max(1, staging_budget_bytes) / plane_bytes)))
        started = time.perf_counter()
        try:
            for oz0 in range(0, int(z_count), int(z_chunk)):
                oz1 = min(int(z_count), oz0 + int(z_chunk))
                upload = _downsample_source_to_upload_slab(
                    source,
                    factors,
                    target_shape,
                    oz0,
                    oz1,
                    algorithm,
                    preserve,
                    intensity_window,
                )
                GL.glTexSubImage3D(
                    GL.GL_TEXTURE_3D,
                    0,
                    0,
                    0,
                    int(oz0),
                    int(x_count),
                    int(y_count),
                    int(oz1 - oz0),
                    upload_format,
                    pixel_type,
                    upload,
                )
                self._yield_stream_build_events()
        except Exception:
            if texture_id:
                GL.glDeleteTextures([int(texture_id)])
            GL.glBindTexture(GL.GL_TEXTURE_3D, 0)
            raise
        self._texture_id = texture_id
        self._volume_data = None
        self._volume_shape = tuple(int(value) for value in target_shape)
        self._volume_cache_key = cache_key
        self._source_shape = source_shape
        self._source_spacing = spacing
        self._upload_needed = False
        self._uploaded_shape = self._volume_shape
        self._uploaded_bytes = int(np.prod(self._volume_shape)) * bytes_per_voxel
        self._uploaded_dtype = upload_dtype_text
        self._last_upload_ms = (time.perf_counter() - started) * 1000.0
        self._preview_stream_build_stats = {
            "backend": "gpu_stream",
            "algorithm": str(algorithm or "hybrid"),
            "preserve_source": bool(preserve),
            "requested_max_dim": int(target_plan["requested_max_dim"]),
            "actual_max_dim": int(max(self._volume_shape) if self._volume_shape else 0),
            "target_max_dim": int(target_plan["target_max_dim"]),
            "source_shape_zyx": tuple(int(value) for value in source_shape),
            "shape_zyx": tuple(int(value) for value in self._volume_shape),
            "factors_zyx": tuple(int(value) for value in factors),
            "bytes": int(self._uploaded_bytes),
            "budget_bytes": int(max(0, self._texture_cache_budget_bytes)),
            "effective_budget_bytes": int(max(0, effective_budget)),
            "staging_budget_bytes": int(max(1, staging_budget_bytes)),
            "staging_chunk_depth": int(z_chunk),
            "texture_format": str(texture_format_name),
            "degraded": bool(target_plan["degraded"]),
            "degrade_reason": str(target_plan["degrade_reason"]),
            "released_active_for_budget": bool(int(old_texture_id or 0) in released_for_budget),
        }
        self._set_preview_texture_provider(
            gpu_texture_preview_provider(
                self._texture_id,
                self._volume_shape,
                self._uploaded_dtype,
                source_shape=self._source_shape,
                spacing_zyx=self._source_spacing,
                cache_key=cache_key,
                build_backend="gpu_stream",
            )
        )
        self._remember_texture(
            cache_key,
            "volume",
            self._texture_id,
            self._uploaded_shape,
            self._uploaded_dtype,
            self._uploaded_bytes,
        )
        if old_texture_id and old_texture_id != texture_id and not self._texture_id_is_cached(old_texture_id) and int(old_texture_id) not in released_for_budget:
            try:
                GL.glDeleteTextures([int(old_texture_id)])
            except Exception:
                pass
        GL.glBindTexture(GL.GL_TEXTURE_3D, 0)
        return self._preview_texture_provider

    def _stream_upload_source_mask_texture(
        self,
        mask,
        max_dim,
        algorithm="occupancy",
        cache_key=None,
        source_shape=None,
        staging_budget_bytes=GPU_VOLUME_STREAM_BUILD_DEFAULT_STAGING_BYTES,
    ):
        source = np.asarray(mask)
        if source.ndim != 3 or min(source.shape) <= 0:
            raise ValueError(f"mask_must_be_non_empty_zyx:{getattr(source, 'shape', ())}")
        if not self._can_stream_build_volume_texture():
            raise RuntimeError(getattr(self._preview_build_capabilities, "reason", "") or "GPU preview build is unavailable")
        source_shape = tuple(int(value) for value in (source_shape or source.shape))
        if len(source_shape) != 3 or min(source_shape) <= 0:
            source_shape = tuple(int(value) for value in source.shape)
        if cache_key is not None and self._activate_cached_texture(cache_key, "mask"):
            self._mask_cache_key = cache_key
            self._mask_data = None
            self._preview_stream_build_stats = dict(getattr(self, "_preview_stream_build_stats", {}) or {})
            self._preview_stream_build_stats["mask"] = {
                "backend": "gpu_cache",
                "cache_hit": True,
                "algorithm": str(algorithm or "occupancy"),
                "requested_max_dim": int(max_dim),
                "actual_max_dim": int(max(self._mask_shape) if self._mask_shape else 0),
                "source_shape_zyx": tuple(int(value) for value in source_shape),
                "shape_zyx": tuple(int(value) for value in self._mask_shape),
                "bytes": int(_preview_shape_bytes(self._mask_shape, 1)),
                "budget_bytes": int(max(0, self._texture_cache_budget_bytes)),
            }
            return True
        target_limit = min(int(max_dim), int(getattr(self._preview_build_capabilities, "max_3d_texture_size", 0) or max_dim))
        effective_budget = self._stream_build_texture_budget_bytes(cache_key=cache_key)
        target_plan = _budget_limited_preview_shape(
            source.shape,
            max(1, target_limit),
            1,
            effective_budget,
            int(getattr(self._preview_build_capabilities, "max_3d_texture_size", 0) or target_limit),
        )
        factors = target_plan["factors"]
        target_shape = target_plan["shape"]
        if len(target_shape) != 3 or min(target_shape) <= 0:
            raise RuntimeError(f"invalid_gpu_mask_preview_shape:{target_shape}")
        z_count, y_count, x_count = target_shape
        old_mask_texture_id = self._mask_texture_id
        self._reserve_texture_cache_bytes(int(target_plan["bytes"]), protected_ids={self._texture_id}, protect_active=True)
        texture_id = self._new_upload_texture_id("mask")
        GL.glActiveTexture(GL.GL_TEXTURE2)
        GL.glBindTexture(GL.GL_TEXTURE_3D, texture_id)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_R, GL.GL_CLAMP_TO_EDGE)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        internal_format, upload_format, pixel_type, texture_format_name = _volume_texture_format(np.uint8)
        GL.glTexImage3D(
            GL.GL_TEXTURE_3D,
            0,
            internal_format,
            int(x_count),
            int(y_count),
            int(z_count),
            0,
            upload_format,
            pixel_type,
            None,
        )
        plane_bytes = max(1, int(y_count) * int(x_count))
        z_chunk = max(1, min(int(z_count), int(max(1, staging_budget_bytes) / plane_bytes)))
        started = time.perf_counter()
        try:
            for oz0 in range(0, int(z_count), int(z_chunk)):
                oz1 = min(int(z_count), oz0 + int(z_chunk))
                upload = _downsample_mask_to_upload_slab(source, factors, target_shape, oz0, oz1, algorithm=algorithm)
                GL.glTexSubImage3D(
                    GL.GL_TEXTURE_3D,
                    0,
                    0,
                    0,
                    int(oz0),
                    int(x_count),
                    int(y_count),
                    int(oz1 - oz0),
                    upload_format,
                    pixel_type,
                    upload,
                )
                self._yield_stream_build_events()
        except Exception:
            if texture_id:
                GL.glDeleteTextures([int(texture_id)])
            GL.glBindTexture(GL.GL_TEXTURE_3D, 0)
            GL.glActiveTexture(GL.GL_TEXTURE0)
            raise
        self._mask_texture_id = texture_id
        self._mask_data = None
        self._mask_shape = tuple(int(value) for value in target_shape)
        self._mask_cache_key = cache_key
        self._mask_upload_needed = False
        self._preview_stream_build_stats = dict(getattr(self, "_preview_stream_build_stats", {}) or {})
        self._preview_stream_build_stats["mask"] = {
            "backend": "gpu_stream",
            "algorithm": str(algorithm or "occupancy"),
            "requested_max_dim": int(target_plan["requested_max_dim"]),
            "actual_max_dim": int(max(self._mask_shape) if self._mask_shape else 0),
            "target_max_dim": int(target_plan["target_max_dim"]),
            "source_shape_zyx": tuple(int(value) for value in source_shape),
            "shape_zyx": tuple(int(value) for value in self._mask_shape),
            "factors_zyx": tuple(int(value) for value in factors),
            "bytes": int(target_plan["bytes"]),
            "budget_bytes": int(max(0, self._texture_cache_budget_bytes)),
            "effective_budget_bytes": int(max(0, effective_budget)),
            "staging_budget_bytes": int(max(1, staging_budget_bytes)),
            "staging_chunk_depth": int(z_chunk),
            "texture_format": str(texture_format_name),
            "degraded": bool(target_plan["degraded"]),
            "degrade_reason": str(target_plan["degrade_reason"]),
            "upload_ms": (time.perf_counter() - started) * 1000.0,
        }
        self._remember_texture(
            cache_key,
            "mask",
            self._mask_texture_id,
            self._mask_shape,
            "uint8",
            int(target_plan["bytes"]),
        )
        if (
            old_mask_texture_id
            and old_mask_texture_id != texture_id
            and not self._texture_id_is_cached(old_mask_texture_id)
        ):
            try:
                GL.glDeleteTextures([int(old_mask_texture_id)])
            except Exception:
                pass
        GL.glBindTexture(GL.GL_TEXTURE_3D, 0)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        return True

    def clear_volume(self):
        self._volume_data = None
        self._volume_shape = ()
        self._volume_cache_key = None
        self._source_shape = ()
        self._source_spacing = ()
        self._upload_needed = False
        self._release_texture_cache()
        self._texture_id = None
        self._mask_data = None
        self._mask_shape = ()
        self._mask_cache_key = None
        self._mask_upload_needed = False
        self._uploaded_shape = ()
        self._uploaded_bytes = 0
        self._last_upload_ms = 0.0
        self._last_draw_ms = 0.0
        self._last_steps = 0
        self._uploaded_dtype = ""
        self._preview_texture_provider = None
        self._preview_stream_build_stats = {}

    def _delete_volume_texture(self):
        if self._initialized and self._texture_id:
            try:
                if not self._texture_id_is_cached(self._texture_id):
                    GL.glDeleteTextures([int(self._texture_id)])
            except Exception:
                pass
        self._texture_id = None
        if self._initialized and self._transfer_lut_texture_id:
            try:
                GL.glDeleteTextures([int(self._transfer_lut_texture_id)])
            except Exception:
                pass
            self._transfer_lut_texture_id = None
            self._transfer_lut_upload_needed = True

    def _delete_mask_texture(self):
        if self._initialized and self._mask_texture_id:
            try:
                if not self._texture_id_is_cached(self._mask_texture_id):
                    GL.glDeleteTextures([int(self._mask_texture_id)])
            except Exception:
                pass
        self._mask_texture_id = None

    def _detach_mask_texture(self):
        self._mask_texture_id = None

    def _texture_record_bytes(self, array):
        try:
            return int(getattr(array, "nbytes", 0) or 0)
        except Exception:
            return 0

    def _texture_cache_record_key(self, key, kind):
        if key is None:
            return None
        return (str(kind or "volume"), repr(key))

    def _texture_cache_owner_from_key(self, key):
        if isinstance(key, tuple) and key:
            owner = key[0]
            if isinstance(owner, tuple):
                return tuple(owner)
        return None

    def _activate_cached_texture(self, key, kind):
        record_key = self._texture_cache_record_key(key, kind)
        if record_key is None:
            return False
        record = self._texture_cache.get(record_key)
        if not record:
            self._texture_cache_misses += 1
            return False
        self._texture_cache.move_to_end(record_key)
        texture_id = int(record.get("texture_id") or 0)
        if kind == "mask":
            self._mask_texture_id = texture_id
            self._mask_shape = tuple(int(value) for value in record.get("shape") or ())
            self._mask_upload_needed = False
        else:
            self._texture_id = texture_id
            self._volume_shape = tuple(int(value) for value in record.get("shape") or ())
            self._uploaded_shape = self._volume_shape
            self._uploaded_bytes = int(record.get("bytes") or 0)
            self._uploaded_dtype = str(record.get("dtype") or "")
            self._upload_needed = False
        self._last_upload_ms = 0.0
        self._texture_cache_hits += 1
        return True

    def _texture_cache_record_for_texture_id(self, texture_id):
        texture_id = int(texture_id or 0)
        if not texture_id:
            return None
        for record in self._texture_cache.values():
            if int(record.get("texture_id") or 0) == texture_id:
                return record
        return None

    def _active_volume_texture_cache_bytes(self, exclude_key=None):
        active_record = self._texture_cache_record_for_texture_id(self._texture_id)
        if not active_record:
            return 0
        exclude_record_key = self._texture_cache_record_key(exclude_key, "volume")
        if exclude_record_key is not None:
            record_key = self._texture_cache_record_key(exclude_key, "volume")
            current_key = None
            for key, record in self._texture_cache.items():
                if record is active_record:
                    current_key = key
                    break
            if current_key == record_key:
                return 0
        return int(active_record.get("bytes") or 0)

    def _stream_build_texture_budget_bytes(self, cache_key=None):
        budget = int(max(0, self._texture_cache_budget_bytes))
        if budget <= 0:
            return 0
        active_bytes = self._active_volume_texture_cache_bytes(exclude_key=cache_key)
        if active_bytes <= 0:
            return budget
        return max(1, budget - int(active_bytes))

    def _reserve_texture_cache_bytes(self, incoming_bytes, protected_ids=None, protect_active=True):
        budget = int(max(0, self._texture_cache_budget_bytes))
        if budget <= 0:
            return set()
        protected = {int(value or 0) for value in (protected_ids or ())}
        if protect_active:
            protected.add(int(self._texture_id or 0))
            protected.add(int(self._mask_texture_id or 0))
        incoming = int(max(0, incoming_bytes))
        deleted_ids = set()
        while self._texture_cache and self._texture_cache_bytes + incoming > budget:
            candidate_key = None
            candidate_record = None
            for record_key, record in self._texture_cache.items():
                texture_id = int(record.get("texture_id") or 0)
                if texture_id in protected:
                    continue
                candidate_key = record_key
                candidate_record = record
                break
            if candidate_key is None or candidate_record is None:
                break
            texture_id = int(candidate_record.get("texture_id") or 0)
            self._texture_cache.pop(candidate_key, None)
            self._texture_cache_bytes = max(0, self._texture_cache_bytes - int(candidate_record.get("bytes") or 0))
            if texture_id:
                try:
                    GL.glDeleteTextures([texture_id])
                    deleted_ids.add(texture_id)
                except Exception:
                    pass
            if texture_id == int(self._texture_id or 0):
                self._texture_id = None
            if texture_id == int(self._mask_texture_id or 0):
                self._mask_texture_id = None
        return deleted_ids

    def _texture_id_is_cached(self, texture_id):
        texture_id = int(texture_id or 0)
        if not texture_id:
            return False
        return any(int(record.get("texture_id") or 0) == texture_id for record in self._texture_cache.values())

    def _new_upload_texture_id(self, kind):
        current_id = int((self._mask_texture_id if kind == "mask" else self._texture_id) or 0)
        if current_id and not self._texture_id_is_cached(current_id):
            return current_id
        return GL.glGenTextures(1)

    def _remember_texture(self, key, kind, texture_id, shape, dtype, byte_count):
        record_key = self._texture_cache_record_key(key, kind)
        if record_key is None or not texture_id:
            return
        if int(max(0, self._texture_cache_budget_bytes)) <= 0:
            return
        old = self._texture_cache.pop(record_key, None)
        if old:
            self._texture_cache_bytes = max(0, self._texture_cache_bytes - int(old.get("bytes") or 0))
            old_id = int(old.get("texture_id") or 0)
            if old_id and old_id != int(texture_id):
                try:
                    GL.glDeleteTextures([old_id])
                except Exception:
                    pass
        record = {
            "texture_id": int(texture_id),
            "kind": str(kind or "volume"),
            "owner": self._texture_cache_owner_from_key(key),
            "shape": tuple(int(value) for value in shape or ()),
            "dtype": str(dtype or ""),
            "bytes": int(max(0, byte_count)),
        }
        self._texture_cache[record_key] = record
        self._texture_cache_bytes += int(record["bytes"])
        self._prune_texture_cache()

    def _prune_texture_cache(self):
        budget = int(max(0, self._texture_cache_budget_bytes))
        while self._texture_cache and (budget <= 0 or self._texture_cache_bytes > budget):
            record_key, record = self._texture_cache_eviction_candidate()
            if record_key is None:
                break
            texture_id = int(record.get("texture_id") or 0)
            self._texture_cache.pop(record_key, None)
            self._texture_cache_bytes = max(0, self._texture_cache_bytes - int(record.get("bytes") or 0))
            if texture_id:
                try:
                    GL.glDeleteTextures([texture_id])
                except Exception:
                    pass

    def _texture_cache_eviction_candidate(self):
        active_ids = {int(self._texture_id or 0), int(self._mask_texture_id or 0)}
        active_owner = self._texture_cache_owner_from_key(self._volume_cache_key)
        candidates = []
        for index, (record_key, record) in enumerate(self._texture_cache.items()):
            texture_id = int(record.get("texture_id") or 0)
            if texture_id in active_ids:
                continue
            owner = record.get("owner")
            kind = str(record.get("kind") or "volume")
            candidates.append(
                (
                    0 if owner != active_owner else 1,
                    0 if kind == "mask" else 1,
                    index,
                    record_key,
                    record,
                )
            )
        if not candidates:
            return None, None
        candidates.sort()
        return candidates[0][3], candidates[0][4]

    def _release_texture_cache(self):
        deleted_ids = set()
        if self._initialized:
            for record in list(self._texture_cache.values()):
                texture_id = int(record.get("texture_id") or 0)
                if texture_id:
                    try:
                        GL.glDeleteTextures([texture_id])
                        deleted_ids.add(texture_id)
                    except Exception:
                        pass
        self._texture_cache = OrderedDict()
        self._texture_cache_bytes = 0
        if int(self._texture_id or 0) in deleted_ids:
            self._texture_id = None
        if int(self._mask_texture_id or 0) in deleted_ids:
            self._mask_texture_id = None

    def release_texture_cache(self):
        self._release_texture_cache()

    def has_volume(self):
        return (self._volume_data is not None or self._texture_id is not None) and not self._failed

    def set_render_state(
        self,
        cutoff_percent,
        yaw,
        pitch,
        zoom,
        render_quality,
        sample_steps=512,
        inside_depth=0.0,
        front_clip=0.0,
        render_mode="still",
        pan_x=0.0,
        pan_y=0.0,
        clarity_mode=False,
        projection_mode="composite",
        mask_mode="image_only",
        mask_opacity=0.45,
        supersample_scale=1.0,
        tint_rgb=(1.0, 0.83, 0.30),
        transfer_preset="amber",
        transfer_opacity=None,
        enhancement=0.0,
        tone_gamma=1.0,
        jitter_strength=None,
        adaptive_step_strength=None,
        gradient_opacity=None,
        gradient_opacity_range=None,
        shader_quality_mode="preset",
        surface_refine=False,
        clip_plane_enabled=False,
        clip_plane_depth=0.0,
        clip_plane_normal=(0.0, 0.0, 1.0),
    ):
        self._cutoff = max(0.0, min(0.98, float(cutoff_percent) / 100.0))
        self._yaw = float(yaw)
        self._pitch = float(pitch)
        self._zoom = max(0.2, float(zoom))
        self._render_quality = max(128, min(GPU_VOLUME_MAX_TEXTURE_DIM, int(render_quality)))
        min_steps = 192 if str(render_mode) == "drag" and str(projection_mode or "").lower() == "composite" else 256
        self._sample_steps = max(min_steps, min(GPU_VOLUME_MAX_RAY_STEPS, int(sample_steps)))
        self._inside_depth = max(0.0, min(1.6, float(inside_depth)))
        self._front_clip = max(0.0, min(0.92, float(front_clip)))
        self._render_mode = "drag" if str(render_mode) == "drag" else "still"
        pan_limit = volume_pan_limit_for_zoom(self._zoom)
        self._pan_x = max(-pan_limit, min(pan_limit, float(pan_x)))
        self._pan_y = max(-pan_limit, min(pan_limit, float(pan_y)))
        self._clarity_mode = bool(clarity_mode)
        projection_mode = str(projection_mode or "composite").lower()
        self._projection_mode = projection_mode if projection_mode in GPU_VOLUME_RENDER_MODES else "composite"
        self._fast_interaction = self._render_mode == "drag" and self._projection_mode == "composite"
        mask_mode = str(mask_mode or "image_only").lower()
        if not self._mask_texture_id or not self._mask_shape:
            mask_mode = "image_only"
        self._mask_mode = mask_mode if mask_mode in GPU_VOLUME_MASK_MODES else "image_only"
        self._mask_opacity = max(0.0, min(1.0, float(mask_opacity)))
        self._enhancement = max(0.0, min(1.0, float(enhancement))) if self._render_mode == "still" else 0.0
        self._tone_gamma = max(0.65, min(1.35, float(tone_gamma)))
        self._surface_refine = bool(surface_refine) and self._render_mode == "still"
        self._clip_plane_enabled = bool(clip_plane_enabled)
        self._clip_plane_depth = max(0.0, min(1.0, float(clip_plane_depth)))
        try:
            normal = tuple(float(value) for value in clip_plane_normal)
        except (TypeError, ValueError):
            normal = (0.0, 0.0, 1.0)
        if len(normal) != 3:
            normal = (0.0, 0.0, 1.0)
        length = math.sqrt(sum(value * value for value in normal))
        if length <= 1e-6:
            normal = (0.0, 0.0, 1.0)
            length = 1.0
        self._clip_plane_normal = tuple(float(value) / length for value in normal)
        self._supersample_scale = max(1.0, min(4.0, float(supersample_scale)))
        try:
            tint = tuple(float(value) for value in tint_rgb)
        except (TypeError, ValueError):
            tint = (1.0, 0.83, 0.30)
        if len(tint) != 3:
            tint = (1.0, 0.83, 0.30)
        self._tint_rgb = tuple(max(0.0, min(1.0, value)) for value in tint)
        self._transfer_preset = str(transfer_preset or "amber").lower()
        if self._transfer_preset not in TRANSFER_PRESET_IDS:
            self._transfer_preset = "amber"
        fallback_quality = volume_shader_quality_settings(
            self._transfer_preset,
            self._render_mode,
            self._projection_mode,
            self._mask_mode,
            self._clip_plane_enabled,
            shader_quality_mode,
        )
        self._shader_quality_mode = str(fallback_quality["shader_quality_mode"])
        fallback_gradient_opacity = float(fallback_quality["gradient_opacity"])
        fallback_gradient_range = tuple(fallback_quality["gradient_opacity_range"])
        if gradient_opacity is None:
            next_gradient_opacity = fallback_gradient_opacity
        else:
            next_gradient_opacity = _coerce_unit_float(gradient_opacity, fallback_gradient_opacity) if self._render_mode == "still" else 0.0
        gradient_low, gradient_high = _coerce_gradient_range(gradient_opacity_range, fallback_gradient_range)
        self._gradient_opacity = next_gradient_opacity
        self._gradient_opacity_range = (gradient_low, gradient_high)
        if jitter_strength is None:
            next_jitter = float(fallback_quality["jitter_strength"])
        else:
            next_jitter = _coerce_unit_float(jitter_strength, float(fallback_quality["jitter_strength"])) if self._render_mode == "still" else 0.0
        self._jitter_strength = next_jitter
        fallback_adaptive = float(fallback_quality["adaptive_step_strength"])
        if adaptive_step_strength is None:
            next_adaptive = fallback_adaptive
        else:
            next_adaptive = _coerce_unit_float(adaptive_step_strength, fallback_adaptive)
        if (
            self._render_mode != "still"
            or self._projection_mode != "composite"
            or self._mask_mode != "image_only"
            or self._clip_plane_enabled
        ):
            next_adaptive = 0.0
        self._adaptive_step_strength = next_adaptive
        if transfer_opacity is None:
            next_opacity = 0.72 if self._clarity_mode and self._render_mode == "still" else (1.0 if self._render_mode == "still" else 0.82)
        else:
            next_opacity = max(0.0, min(1.4, float(transfer_opacity)))
        next_lut = build_volume_transfer_lut(
            self._transfer_preset,
            self._tint_rgb,
            cutoff=0.0,
            opacity=next_opacity,
            clarity=self._clarity_mode and self._render_mode == "still",
        )
        if self._transfer_lut_data is None or not np.array_equal(self._transfer_lut_data, next_lut):
            self._transfer_lut_data = next_lut
            self._transfer_lut_upload_needed = True
        self._transfer_opacity = float(next_opacity)

    def render_stats(self):
        return {
            "mode": self._render_mode,
            "shape_zyx": tuple(int(value) for value in self._uploaded_shape),
            "bytes": int(self._uploaded_bytes),
            "upload_ms": float(self._last_upload_ms),
            "draw_ms": float(self._last_draw_ms),
            "steps": int(self._last_steps),
            "dtype": self._uploaded_dtype,
            "clarity": bool(self._clarity_mode),
            "texture_filter": _texture_filter_name(self._clarity_mode, self._render_mode, self._clip_plane_enabled),
            "display_scaling": _display_scaling_name(self._clarity_mode, self._render_mode, self._clip_plane_enabled),
            "projection_mode": self._projection_mode,
            "mask_mode": self._mask_mode,
            "mask_shape_zyx": tuple(int(value) for value in self._mask_shape),
            "enhancement": float(getattr(self, "_enhancement", 0.0)),
            "tone_gamma": float(getattr(self, "_tone_gamma", 1.0)),
            "shader_quality_mode": str(getattr(self, "_shader_quality_mode", "preset")),
            "jitter_strength": float(getattr(self, "_jitter_strength", 0.0)),
            "adaptive_step_strength": float(getattr(self, "_adaptive_step_strength", 0.0)),
            "gradient_opacity": float(getattr(self, "_gradient_opacity", 0.0)),
            "gradient_opacity_range": tuple(float(value) for value in getattr(self, "_gradient_opacity_range", (0.04, 0.34))),
            "surface_refine": bool(getattr(self, "_surface_refine", False)),
            "clip_plane_enabled": bool(getattr(self, "_clip_plane_enabled", False)),
            "clip_plane_depth": float(getattr(self, "_clip_plane_depth", 0.0)),
            "clip_plane_normal": tuple(float(value) for value in getattr(self, "_clip_plane_normal", (0.0, 0.0, 1.0))),
            "supersample_scale": float(self._supersample_scale),
            "tint_rgb": tuple(float(value) for value in getattr(self, "_tint_rgb", (1.0, 0.83, 0.30))),
            "transfer_preset": getattr(self, "_transfer_preset", "amber"),
            "transfer_opacity": float(getattr(self, "_transfer_opacity", 1.0)),
            "transfer_lut": tuple(int(value) for value in getattr(self, "_transfer_lut_data", np.zeros((1, 0, 4), dtype=np.uint8)).shape),
            "texture_cache_entries": int(len(getattr(self, "_texture_cache", {}) or {})),
            "texture_cache_bytes": int(getattr(self, "_texture_cache_bytes", 0) or 0),
            "texture_cache_budget_bytes": int(getattr(self, "_texture_cache_budget_bytes", 0) or 0),
            "texture_cache_hits": int(getattr(self, "_texture_cache_hits", 0) or 0),
            "texture_cache_misses": int(getattr(self, "_texture_cache_misses", 0) or 0),
            "gpu_preview_build": self._preview_build_capabilities.to_stats(),
            "gpu_stream_build": dict(getattr(self, "_preview_stream_build_stats", {}) or {}),
            "preview_provider": self._preview_provider_stats(),
        }

    def renderer_label(self):
        return self._renderer_label

    def render_scale(self):
        return float(self._supersample_scale)

    def renderer_details(self):
        return self._renderer_details or self._renderer_label

    def _initialize_render_core(self):
        self._apply_clear_color()
        GL.glDisable(GL.GL_DEPTH_TEST)
        self._update_renderer_label()
        self._preview_build_capabilities = probe_gpu_preview_build_capabilities()
        self._program = _link_program(_VERTEX_SHADER, _FRAGMENT_SHADER)
        vertices = np.array([-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0], dtype=np.float32)
        self._quad_vbo = GL.glGenBuffers(1)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._quad_vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL.GL_STATIC_DRAW)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        self._initialized = True
        self._upload_volume_if_needed()
        self._upload_mask_if_needed()
        self._upload_transfer_lut_if_needed()

    def _update_renderer_label(self):
        vendor = _decode_gl_string(GL.glGetString(GL.GL_VENDOR))
        renderer = _decode_gl_string(GL.glGetString(GL.GL_RENDERER))
        version = _decode_gl_string(GL.glGetString(GL.GL_VERSION))
        label = _compact_renderer_text(renderer or vendor)
        self._renderer_label = label
        self._renderer_details = " | ".join(part for part in (vendor, renderer, version) if part)

    def _upload_volume_if_needed(self):
        if not self._upload_needed or self._volume_data is None:
            return
        depth, height, width = self._volume_shape
        self._texture_id = self._new_upload_texture_id("volume")
        GL.glBindTexture(GL.GL_TEXTURE_3D, self._texture_id)
        texture_filter = GL.GL_NEAREST if _crisp_sampling_enabled(self._clarity_mode, self._render_mode, self._clip_plane_enabled) else GL.GL_LINEAR
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MIN_FILTER, texture_filter)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MAG_FILTER, texture_filter)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_R, GL.GL_CLAMP_TO_EDGE)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        internal_format, upload_format, pixel_type, _texture_format_name = _volume_texture_format(self._volume_data.dtype)
        started = time.perf_counter()
        GL.glTexImage3D(
            GL.GL_TEXTURE_3D,
            0,
            internal_format,
            int(width),
            int(height),
            int(depth),
            0,
            upload_format,
            pixel_type,
            self._volume_data,
        )
        self._last_upload_ms = (time.perf_counter() - started) * 1000.0
        self._uploaded_shape = (int(depth), int(height), int(width))
        self._uploaded_bytes = int(self._volume_data.nbytes)
        self._uploaded_dtype = str(self._volume_data.dtype)
        self._remember_texture(
            self._volume_cache_key,
            "volume",
            self._texture_id,
            self._uploaded_shape,
            self._uploaded_dtype,
            self._uploaded_bytes,
        )
        GL.glBindTexture(GL.GL_TEXTURE_3D, 0)
        self._upload_needed = False

    def _upload_mask_if_needed(self):
        if not self._mask_upload_needed or self._mask_data is None:
            return
        depth, height, width = self._mask_shape
        self._mask_texture_id = self._new_upload_texture_id("mask")
        GL.glActiveTexture(GL.GL_TEXTURE2)
        GL.glBindTexture(GL.GL_TEXTURE_3D, self._mask_texture_id)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_R, GL.GL_CLAMP_TO_EDGE)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        GL.glTexImage3D(
            GL.GL_TEXTURE_3D,
            0,
            GL.GL_LUMINANCE,
            int(width),
            int(height),
            int(depth),
            0,
            GL.GL_LUMINANCE,
            GL.GL_UNSIGNED_BYTE,
            self._mask_data,
        )
        self._remember_texture(
            self._mask_cache_key,
            "mask",
            self._mask_texture_id,
            self._mask_shape,
            "uint8",
            int(getattr(self._mask_data, "nbytes", 0) or 0),
        )
        GL.glBindTexture(GL.GL_TEXTURE_3D, 0)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        self._mask_upload_needed = False

    def _upload_transfer_lut_if_needed(self):
        if not self._transfer_lut_upload_needed or self._transfer_lut_data is None:
            return
        if not self._transfer_lut_texture_id:
            self._transfer_lut_texture_id = GL.glGenTextures(1)
        lut = np.ascontiguousarray(self._transfer_lut_data, dtype=np.uint8)
        height, width = int(lut.shape[0]), int(lut.shape[1])
        GL.glActiveTexture(GL.GL_TEXTURE1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._transfer_lut_texture_id)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D,
            0,
            GL.GL_RGBA,
            width,
            height,
            0,
            GL.GL_RGBA,
            GL.GL_UNSIGNED_BYTE,
            lut,
        )
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        self._transfer_lut_upload_needed = False

    def _draw_volume(self, viewport_width, viewport_height):
        if not self._program or not self._quad_vbo or not self._texture_id:
            return
        self._upload_mask_if_needed()
        self._upload_transfer_lut_if_needed()
        GL.glUseProgram(self._program)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_3D, self._texture_id)
        texture_filter = GL.GL_NEAREST if _crisp_sampling_enabled(self._clarity_mode, self._render_mode, self._clip_plane_enabled) else GL.GL_LINEAR
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MIN_FILTER, texture_filter)
        GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MAG_FILTER, texture_filter)
        self._set_uniform_int("u_volume", 0)
        GL.glActiveTexture(GL.GL_TEXTURE1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._transfer_lut_texture_id)
        self._set_uniform_int("u_transfer_lut", 1)
        GL.glActiveTexture(GL.GL_TEXTURE2)
        mask_mode = self._mask_mode if self._mask_texture_id and self._mask_shape else "image_only"
        GL.glBindTexture(GL.GL_TEXTURE_3D, self._mask_texture_id or self._texture_id)
        self._set_uniform_int("u_mask", 2)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        self._set_uniform_float("u_cutoff", self._cutoff)
        self._set_uniform_float("u_zoom", self._zoom)
        self._set_uniform_vec2("u_pan", self._pan_x, self._pan_y)
        self._set_uniform_float("u_front_clip", self._front_clip)
        self._set_uniform_int("u_projection_mode", GPU_VOLUME_RENDER_MODES.get(self._projection_mode, 0))
        self._set_uniform_int("u_mask_mode", GPU_VOLUME_MASK_MODES.get(mask_mode, 0))
        self._set_uniform_float("u_mask_opacity", self._mask_opacity)
        clarity = 1.0 if self._clarity_mode and self._render_mode == "still" else 0.0
        self._set_uniform_float("u_clarity", clarity)
        self._set_uniform_float("u_enhancement", self._enhancement)
        self._set_uniform_float("u_tone_gamma", self._tone_gamma)
        self._set_uniform_float("u_jitter_strength", self._jitter_strength)
        self._set_uniform_float("u_adaptive_step_strength", self._adaptive_step_strength)
        self._set_uniform_float("u_gradient_opacity", self._gradient_opacity)
        self._set_uniform_vec2("u_gradient_opacity_range", *self._gradient_opacity_range)
        self._set_uniform_vec3("u_tint_rgb", *self._tint_rgb)
        self._set_uniform_int("u_surface_refine", 1 if self._surface_refine else 0)
        self._set_uniform_int("u_fast_interaction", 1 if self._fast_interaction else 0)
        self._set_uniform_int("u_clip_plane_enabled", 1 if self._clip_plane_enabled else 0)
        self._set_uniform_float("u_clip_plane_depth", self._clip_plane_depth)
        self._set_uniform_vec3("u_clip_plane_normal", *self._clip_plane_normal)
        self._set_uniform_float("u_opacity", max(0.0, min(1.4, float(getattr(self, "_transfer_opacity", 1.0)))))
        self._set_uniform_float("u_gradient_weight", 1.35 if clarity > 0.0 else (1.0 if self._render_mode == "still" else 0.72))
        min_steps = 192 if self._fast_interaction else 256
        steps = max(min_steps, min(GPU_VOLUME_MAX_RAY_STEPS, int(self._sample_steps)))
        self._last_steps = int(steps)
        self._set_uniform_int("u_steps", steps)
        self._set_uniform_float("u_step_size", 1.58 / float(steps))
        self._set_uniform_vec2("u_viewport", float(max(1, int(viewport_width))), float(max(1, int(viewport_height))))
        depth, height, width = self._volume_shape
        x_scale, y_scale, z_scale = volume_shape_scale(self._source_shape or self._volume_shape, self._source_spacing)
        self._set_uniform_vec3("u_shape_scale", x_scale, y_scale, z_scale)
        self._set_uniform_vec3("u_texel_step", 1.0 / max(float(width), 1.0), 1.0 / max(float(height), 1.0), 1.0 / max(float(depth), 1.0))
        inv_rotation = _rotation_inverse_matrix(self._yaw, self._pitch)
        camera_distance = camera_distance_for_inside_zoom((x_scale, y_scale, z_scale), inv_rotation, self._zoom, self._inside_depth)
        self._set_uniform_float("u_camera_distance", camera_distance)
        loc = GL.glGetUniformLocation(self._program, "u_inv_rotation")
        if loc >= 0:
            GL.glUniformMatrix3fv(loc, 1, GL.GL_TRUE, inv_rotation)

        attr = GL.glGetAttribLocation(self._program, "a_position")
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._quad_vbo)
        GL.glEnableVertexAttribArray(attr)
        GL.glVertexAttribPointer(attr, 2, GL.GL_FLOAT, False, 0, None)
        started = time.perf_counter()
        GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)
        GL.glFlush()
        self._last_draw_ms = (time.perf_counter() - started) * 1000.0
        GL.glDisableVertexAttribArray(attr)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        GL.glBindTexture(GL.GL_TEXTURE_3D, 0)
        GL.glActiveTexture(GL.GL_TEXTURE1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        GL.glActiveTexture(GL.GL_TEXTURE2)
        GL.glBindTexture(GL.GL_TEXTURE_3D, 0)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glUseProgram(0)

    def _set_uniform_float(self, name, value):
        loc = GL.glGetUniformLocation(self._program, name)
        if loc >= 0:
            GL.glUniform1f(loc, float(value))

    def _set_uniform_int(self, name, value):
        loc = GL.glGetUniformLocation(self._program, name)
        if loc >= 0:
            GL.glUniform1i(loc, int(value))

    def _set_uniform_vec2(self, name, x, y):
        loc = GL.glGetUniformLocation(self._program, name)
        if loc >= 0:
            GL.glUniform2f(loc, float(x), float(y))

    def _set_uniform_vec3(self, name, x, y, z):
        loc = GL.glGetUniformLocation(self._program, name)
        if loc >= 0:
            GL.glUniform3f(loc, float(x), float(y), float(z))

    def _release_render_core(self):
        if not self._initialized:
            return
        self._release_texture_cache()
        if self._texture_id:
            GL.glDeleteTextures([int(self._texture_id)])
            self._texture_id = None
        if self._mask_texture_id:
            GL.glDeleteTextures([int(self._mask_texture_id)])
            self._mask_texture_id = None
        if self._transfer_lut_texture_id:
            GL.glDeleteTextures([int(self._transfer_lut_texture_id)])
            self._transfer_lut_texture_id = None
        if self._quad_vbo:
            GL.glDeleteBuffers(1, [int(self._quad_vbo)])
            self._quad_vbo = None
        if self._program:
            GL.glDeleteProgram(self._program)
            self._program = None
        GL.glBindTexture(GL.GL_TEXTURE_3D, 0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        GL.glUseProgram(0)
        GL.glFinish()
        self._initialized = False


if gpu_volume_offscreen_available():

    class TifGpuVolumeOffscreenRenderer(_GpuVolumeRenderCore):
        """GPU ray marcher that renders into an FBO instead of a top-level widget."""

        def __init__(self):
            self._init_render_state()
            self._context = None
            self._surface = None
            self._fbo = None
            self._color_texture = None
            self._fbo_size = (0, 0)

        def initialize(self):
            if self._initialized and self._context is not None:
                return
            fmt = QSurfaceFormat()
            fmt.setDepthBufferSize(0)
            fmt.setStencilBufferSize(0)
            fmt.setSwapBehavior(QSurfaceFormat.SingleBuffer)
            context = QOpenGLContext()
            context.setFormat(fmt)
            if not context.create():
                raise RuntimeError("OpenGL offscreen context creation failed")
            surface = QOffscreenSurface()
            surface.setFormat(context.format())
            surface.create()
            if not surface.isValid():
                raise RuntimeError("OpenGL offscreen surface creation failed")
            if not context.makeCurrent(surface):
                raise RuntimeError("OpenGL offscreen context makeCurrent failed")
            self._context = context
            self._surface = surface
            try:
                self._initialize_render_core()
            except Exception:
                context.doneCurrent()
                raise
            context.doneCurrent()

        def set_volume_data(self, volume, source_shape=None, spacing_zyx=None, cache_key=None):
            return self._store_volume_data(volume, source_shape=source_shape, spacing_zyx=spacing_zyx, cache_key=cache_key)

        def build_volume_texture_from_source(self, volume, max_dim, algorithm="hybrid", preserve_source=False, cache_key=None, source_shape=None, spacing_zyx=None):
            self.initialize()
            if not self._context.makeCurrent(self._surface):
                raise RuntimeError("OpenGL offscreen context makeCurrent failed")
            try:
                return self._stream_upload_source_volume_texture(
                    volume,
                    max_dim,
                    algorithm=algorithm,
                    preserve_source=preserve_source,
                    cache_key=cache_key,
                    source_shape=source_shape,
                    spacing_zyx=spacing_zyx,
                )
            finally:
                self._context.doneCurrent()

        def set_mask_data(self, mask, cache_key=None):
            return self._store_mask_data(mask, cache_key=cache_key)

        def build_mask_texture_from_source(self, mask, max_dim, algorithm="occupancy", cache_key=None, source_shape=None):
            self.initialize()
            if not self._context.makeCurrent(self._surface):
                raise RuntimeError("OpenGL offscreen context makeCurrent failed")
            try:
                return self._stream_upload_source_mask_texture(
                    mask,
                    max_dim,
                    algorithm=algorithm,
                    cache_key=cache_key,
                    source_shape=source_shape,
                )
            finally:
                self._context.doneCurrent()

        def render_image(self, width, height):
            display_width = max(1, int(width))
            display_height = max(1, int(height))
            scale = max(1.0, min(4.0, float(self.render_scale())))
            width = max(1, int(round(display_width * scale)))
            height = max(1, int(round(display_height * scale)))
            self.initialize()
            if self._failed or not self.has_volume() or not self._volume_shape:
                return None
            if not self._context.makeCurrent(self._surface):
                raise RuntimeError("OpenGL offscreen context makeCurrent failed")
            try:
                self._ensure_fbo(width, height)
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self._fbo)
                GL.glViewport(0, 0, width, height)
                self._apply_clear_color()
                GL.glClear(GL.GL_COLOR_BUFFER_BIT)
                self._upload_volume_if_needed()
                self._draw_volume(width, height)
                GL.glPixelStorei(GL.GL_PACK_ALIGNMENT, 1)
                pixels = GL.glReadPixels(0, 0, width, height, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
                image_data = np.frombuffer(pixels, dtype=np.uint8).reshape((height, width, 4))
                image_data = np.ascontiguousarray(image_data[::-1])
                return QImage(image_data.data, width, height, width * 4, QImage.Format_RGBA8888).copy()
            finally:
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
                self._context.doneCurrent()

        def _ensure_fbo(self, width, height):
            size = (max(1, int(width)), max(1, int(height)))
            if self._fbo and self._color_texture and self._fbo_size == size:
                return
            self._release_fbo()
            self._color_texture = GL.glGenTextures(1)
            GL.glBindTexture(GL.GL_TEXTURE_2D, self._color_texture)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
            GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, size[0], size[1], 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, None)
            self._fbo = GL.glGenFramebuffers(1)
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self._fbo)
            GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_TEXTURE_2D, self._color_texture, 0)
            status = GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
            if status != GL.GL_FRAMEBUFFER_COMPLETE:
                self._release_fbo()
                raise RuntimeError(f"OpenGL offscreen framebuffer incomplete: {status}")
            self._fbo_size = size

        def _release_fbo(self):
            if self._color_texture:
                GL.glDeleteTextures([int(self._color_texture)])
                self._color_texture = None
            if self._fbo:
                GL.glDeleteFramebuffers(1, [int(self._fbo)])
                self._fbo = None
            self._fbo_size = (0, 0)

        def clear_volume(self):
            if self._context is not None and self._surface is not None and self._context.makeCurrent(self._surface):
                try:
                    super().clear_volume()
                finally:
                    self._context.doneCurrent()
            else:
                self._volume_data = None
                self._volume_shape = ()
                self._source_shape = ()
                self._source_spacing = ()
                self._upload_needed = False
                self._texture_id = None
                self._mask_texture_id = None
                self._mask_data = None
                self._mask_shape = ()
                self._mask_upload_needed = False
                self._transfer_lut_texture_id = None
                self._transfer_lut_upload_needed = True
                self._uploaded_shape = ()
                self._uploaded_bytes = 0
                self._last_upload_ms = 0.0
                self._last_draw_ms = 0.0
                self._last_steps = 0
                self._uploaded_dtype = ""
                self._preview_texture_provider = None
                self._preview_stream_build_stats = {}

        def release(self):
            if self._context is not None and self._surface is not None and self._context.makeCurrent(self._surface):
                try:
                    self._release_fbo()
                    self._release_render_core()
                finally:
                    self._context.doneCurrent()
            self._surface = None
            self._context = None

    class TifGpuVolumeOffscreenWidget(QLabel):
        """QLabel facade for the offscreen GPU renderer.

        The top-level Qt window only sees a normal label and pixmap; OpenGL work
        happens on a QOffscreenSurface, so QWebEngine/Agent composition stays
        compatible with the TIF workbench.
        """

        render_failed = Signal(str)
        render_info_changed = Signal(str)
        render_stats_changed = Signal()

        def __init__(self, parent=None):
            super().__init__(parent)
            self._renderer = TifGpuVolumeOffscreenRenderer()
            self.workbench = None
            self._mouse_mode = ""
            self._last_drag_pos = None
            self._empty_text = "No TIF volume loaded"
            self._failed = False
            self._batch_update_depth = 0
            self._batch_render_pending = False
            self._interaction_render_scheduled = False
            self._interaction_render_delay_ms = 16
            self._last_renderer_info = ""
            self._axis_overlays = []
            self.setObjectName("tifVolumeCanvas")
            self.setAlignment(Qt.AlignCenter)
            self.setMinimumSize(360, 280)
            self.setFocusPolicy(Qt.StrongFocus)
            self.setFrameShape(QFrame.NoFrame)
            self.setText(self._empty_text)

        def set_theme(self, theme):
            self._renderer.set_theme(theme)
            self.update()

        def _try_start_local_axis_endpoint_drag(self, event):
            if self.workbench is None or event.button() != Qt.LeftButton:
                return False
            handler = getattr(self.workbench, "start_local_axis_endpoint_drag", None)
            if not callable(handler):
                return False
            if not handler(event.position().x(), event.position().y()):
                return False
            self._mouse_mode = "local_axis_endpoint"
            self._last_drag_pos = event.position()
            event.accept()
            return True

        def setText(self, text):
            self._empty_text = str(text or "")
            super().setText(self._empty_text)

        def initialize_renderer(self, emit_info=True):
            self._renderer.initialize()
            if emit_info:
                self._emit_renderer_info()

        def clear(self):
            self.clear_volume()

        def clear_volume(self):
            self._renderer.clear_volume()
            self._axis_overlays = []
            super().clear()
            super().setText(self._empty_text)
            self.render_stats_changed.emit()

        def set_axis_overlays(self, overlays):
            self._axis_overlays = list(overlays or [])
            self.update()

        def has_volume(self):
            return self._renderer.has_volume() and not self._failed

        def set_volume_data(self, volume, source_shape=None, spacing_zyx=None, cache_key=None):
            try:
                self._renderer.set_volume_data(volume, source_shape=source_shape, spacing_zyx=spacing_zyx, cache_key=cache_key)
                self._emit_renderer_info()
                self._request_render_to_label()
            except Exception as exc:
                self._mark_failed(f"GPU offscreen texture upload failed: {exc}")

        def build_volume_texture_from_source(self, volume, max_dim, algorithm="hybrid", preserve_source=False, cache_key=None, source_shape=None, spacing_zyx=None):
            try:
                provider = self._renderer.build_volume_texture_from_source(
                    volume,
                    max_dim,
                    algorithm=algorithm,
                    preserve_source=preserve_source,
                    cache_key=cache_key,
                    source_shape=source_shape,
                    spacing_zyx=spacing_zyx,
                )
                self._emit_renderer_info()
                self._request_render_to_label()
                return provider
            except Exception as exc:
                self._mark_failed(f"GPU streamed preview build failed: {exc}")
                raise

        def set_mask_data(self, mask, cache_key=None):
            try:
                self._renderer.set_mask_data(mask, cache_key=cache_key)
                self._request_render_to_label()
            except Exception as exc:
                self._mark_failed(f"GPU offscreen mask upload failed: {exc}")

        def build_mask_texture_from_source(self, mask, max_dim, algorithm="occupancy", cache_key=None, source_shape=None):
            try:
                result = self._renderer.build_mask_texture_from_source(
                    mask,
                    max_dim,
                    algorithm=algorithm,
                    cache_key=cache_key,
                    source_shape=source_shape,
                )
                self._emit_renderer_info()
                self._request_render_to_label()
                return result
            except Exception as exc:
                self._mark_failed(f"GPU streamed mask preview build failed: {exc}")
                raise

        def set_render_state(self, *args, **kwargs):
            try:
                self._renderer.set_render_state(*args, **kwargs)
                self._request_render_to_label()
            except Exception as exc:
                self._mark_failed(f"GPU offscreen render failed: {exc}")

        def set_interaction_render_state(self, *args, **kwargs):
            try:
                self._renderer.set_render_state(*args, **kwargs)
                self._request_interaction_render_to_label()
            except Exception as exc:
                self._mark_failed(f"GPU offscreen interaction render failed: {exc}")

        def set_volume_render_inputs(self, volume, mask=None, render_state=None, source_shape=None, spacing_zyx=None, volume_cache_key=None, mask_cache_key=None):
            self._batch_update_depth += 1
            try:
                self.set_volume_data(volume, source_shape=source_shape, spacing_zyx=spacing_zyx, cache_key=volume_cache_key)
                self.set_mask_data(mask, cache_key=mask_cache_key)
                if render_state is not None:
                    self.set_render_state(**dict(render_state))
            finally:
                self._batch_update_depth = max(0, self._batch_update_depth - 1)
            if self._batch_render_pending:
                self._batch_render_pending = False
                self._render_to_label()

        def render_stats(self):
            return self._renderer.render_stats()

        def release_texture_cache(self):
            try:
                self._renderer.release_texture_cache()
                self.render_stats_changed.emit()
            except Exception as exc:
                self._mark_failed(f"GPU offscreen texture cache release failed: {exc}")

        def renderer_label(self):
            return self._renderer.renderer_label()

        def set_stream_build_yield_callback(self, callback):
            self._renderer.set_stream_build_yield_callback(callback)

        def _emit_renderer_info(self):
            details = self._renderer.renderer_details()
            if details and details != self._last_renderer_info:
                self._last_renderer_info = details
                self.render_info_changed.emit(details)

        def _request_render_to_label(self):
            if self._batch_update_depth > 0:
                self._batch_render_pending = True
                return
            self._render_to_label()

        def _request_interaction_render_to_label(self):
            if self._batch_update_depth > 0:
                self._batch_render_pending = True
                return
            if self._interaction_render_scheduled:
                return
            self._interaction_render_scheduled = True

            def run():
                self._interaction_render_scheduled = False
                self._render_to_label()

            QTimer.singleShot(int(self._interaction_render_delay_ms), run)

        def _render_to_label(self):
            if self._failed or not self._renderer.has_volume():
                return
            image = self._renderer.render_image(max(1, self.width()), max(1, self.height()))
            if image is None:
                return
            pixmap = QPixmap.fromImage(image)
            if pixmap.width() != max(1, self.width()) or pixmap.height() != max(1, self.height()):
                transform = (
                    Qt.FastTransformation
                    if _crisp_sampling_enabled(
                        self._renderer._clarity_mode,
                        self._renderer._render_mode,
                        self._renderer._clip_plane_enabled,
                    )
                    else Qt.SmoothTransformation
                )
                pixmap = pixmap.scaled(max(1, self.width()), max(1, self.height()), Qt.KeepAspectRatio, transform)
            self.setPixmap(pixmap)
            self.render_stats_changed.emit()

        def paintEvent(self, event):
            super().paintEvent(event)
            if not self._axis_overlays or self.pixmap() is None or self.pixmap().isNull():
                return
            painter = QPainter(self)
            try:
                self._draw_axis_overlays(painter)
            finally:
                painter.end()

        def _draw_axis_overlays(self, painter):
            painter.setRenderHint(QPainter.Antialiasing, True)
            font = painter.font()
            font.setPointSize(9)
            painter.setFont(font)
            for overlay in self._axis_overlays:
                if overlay.get("kind") == "point":
                    point = overlay.get("point_xy")
                    if not point:
                        continue
                    color = QColor(str(overlay.get("color") or "#FFFFFF"))
                    x, y = float(point[0]), float(point[1])
                    radius = int(overlay.get("radius", 5))
                    painter.setPen(QPen(color, 2))
                    painter.setBrush(_volume_overlay_color(150, self._renderer.current_theme))
                    painter.drawEllipse(int(round(x - radius)), int(round(y - radius)), radius * 2, radius * 2)
                    label = str(overlay.get("label") or "")
                    if label:
                        dx, dy = overlay.get("label_offset_xy") or (8, -8)
                        self._draw_axis_label(painter, label, x + float(dx), y + float(dy), color, str(overlay.get("label_position") or "right"))
                    continue
                start = overlay.get("start_xy")
                end = overlay.get("end_xy")
                if not start or not end:
                    continue
                color = QColor(str(overlay.get("color") or "#FFB84D"))
                painter.setPen(QPen(color, int(overlay.get("width", 2))))
                x0, y0 = float(start[0]), float(start[1])
                x1, y1 = float(end[0]), float(end[1])
                painter.drawLine(int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1)))
                role = str(overlay.get("role") or "")
                handle_radius = 6 if role == "editable_output" else 3
                if role == "editable_output":
                    painter.setBrush(_volume_overlay_color(185, self._renderer.current_theme))
                else:
                    painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(
                    int(round(x0 - handle_radius)),
                    int(round(y0 - handle_radius)),
                    handle_radius * 2,
                    handle_radius * 2,
                )
                painter.drawEllipse(
                    int(round(x1 - handle_radius)),
                    int(round(y1 - handle_radius)),
                    handle_radius * 2,
                    handle_radius * 2,
                )
                label = str(overlay.get("label") or "")
                if label:
                    anchor = overlay.get("label_anchor_xy") or end
                    dx, dy = overlay.get("label_offset_xy") or (8, -8)
                    self._draw_axis_label(
                        painter,
                        label,
                        float(anchor[0]) + float(dx),
                        float(anchor[1]) + float(dy),
                        color,
                        str(overlay.get("label_position") or "right"),
                    )

        def _draw_axis_label(self, painter, text, x, y, color, position="right"):
            metrics = painter.fontMetrics()
            padding_x = 6
            padding_y = 3
            text_w = metrics.horizontalAdvance(text)
            text_h = metrics.height()
            rect_x = float(x)
            rect_y = float(y) - text_h - padding_y
            if str(position) == "left":
                rect_x -= text_w + padding_x * 2
            elif str(position) == "center":
                rect_x -= (text_w + padding_x * 2) / 2.0
            rect = QRect(
                int(round(rect_x)),
                int(round(rect_y)),
                int(round(text_w + padding_x * 2)),
                int(round(text_h + padding_y * 2)),
            )
            bounds = self.rect().adjusted(2, 2, -2, -2)
            if rect.right() > bounds.right():
                rect.moveRight(bounds.right())
            if rect.left() < bounds.left():
                rect.moveLeft(bounds.left())
            if rect.top() < bounds.top():
                rect.moveTop(bounds.top())
            if rect.bottom() > bounds.bottom():
                rect.moveBottom(bounds.bottom())
            painter.fillRect(rect, _volume_overlay_color(205, self._renderer.current_theme))
            painter.setPen(QPen(color, 1))
            painter.drawRect(rect.adjusted(0, 0, -1, -1))
            painter.setPen(QColor("#F4F7F9"))
            painter.drawText(rect.adjusted(padding_x, padding_y, -padding_x, -padding_y), Qt.AlignLeft | Qt.AlignVCenter, text)

        def resizeEvent(self, event):
            super().resizeEvent(event)
            try:
                self._render_to_label()
            except Exception as exc:
                self._mark_failed(f"GPU offscreen resize render failed: {exc}")

        def _mark_failed(self, reason):
            if self._failed:
                return
            self._failed = True
            self.render_failed.emit(str(reason or "GPU offscreen volume renderer failed"))

        def mousePressEvent(self, event):
            self.setFocus(Qt.MouseFocusReason)
            if self.workbench is not None and event.button() == Qt.LeftButton:
                picker = getattr(self.workbench, "pick_local_axis_roll_reference_at", None)
                if callable(picker) and picker(event.position().x(), event.position().y()):
                    event.accept()
                    return
            if self._try_start_local_axis_endpoint_drag(event):
                return
            if self.workbench is not None and event.button() in (Qt.LeftButton, Qt.RightButton):
                self._mouse_mode = "rotate" if event.button() == Qt.LeftButton else "pan"
                self._last_drag_pos = event.position()
                event.accept()
                return
            super().mousePressEvent(event)

        def mouseMoveEvent(self, event):
            buttons = event.buttons()
            active = (
                (self._mouse_mode == "rotate" and buttons & Qt.LeftButton)
                or (self._mouse_mode == "local_axis_endpoint" and buttons & Qt.LeftButton)
                or (self._mouse_mode == "pan" and buttons & Qt.RightButton)
            )
            if self.workbench is not None and active and self._last_drag_pos is not None:
                current = event.position()
                dx = current.x() - self._last_drag_pos.x()
                dy = current.y() - self._last_drag_pos.y()
                self._last_drag_pos = current
                if self._mouse_mode == "local_axis_endpoint":
                    self.workbench.drag_local_axis_endpoint(current.x(), current.y())
                elif self._mouse_mode == "pan":
                    self.workbench.pan_volume_preview(dx, dy)
                else:
                    self.workbench.rotate_volume_preview(dx, dy)
                event.accept()
                return
            super().mouseMoveEvent(event)

        def mouseReleaseEvent(self, event):
            if event.button() in (Qt.LeftButton, Qt.RightButton) and self._mouse_mode:
                if self._mouse_mode == "local_axis_endpoint" and self.workbench is not None:
                    self.workbench.finish_local_axis_endpoint_drag()
                self._mouse_mode = ""
                self._last_drag_pos = None
                if self.workbench is not None:
                    self.workbench.finish_volume_interaction_debounced()
                event.accept()
                return
            super().mouseReleaseEvent(event)

        def wheelEvent(self, event):
            if self.workbench is None:
                event.ignore()
                return
            delta = event.angleDelta().y()
            if delta == 0:
                event.ignore()
                return
            self.workbench.zoom_volume_preview(1 if delta > 0 else -1)
            event.accept()

        def release_gl_resources(self):
            self._renderer.release()

        def delete_texture(self):
            self.release_gl_resources()

        def closeEvent(self, event):
            self.release_gl_resources()
            super().closeEvent(event)

else:
    TifGpuVolumeOffscreenRenderer = None
    TifGpuVolumeOffscreenWidget = None


if gpu_volume_canvas_available():

    class TifGpuVolumeCanvas(QOpenGLWidget):
        """Read-only GPU volume preview canvas.

        The widget owns only a normalized, downsampled preview texture. It never
        receives or mutates label volumes.
        """

        render_failed = Signal(str)
        render_info_changed = Signal(str)
        render_stats_changed = Signal()

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName("tifVolumeCanvas")
            self.setMinimumSize(360, 280)
            self.setFocusPolicy(Qt.StrongFocus)
            self.workbench = None
            self._empty_text = "No TIF volume loaded"
            self._volume_data = None
            self._volume_shape = ()
            self._volume_cache_key = None
            self._source_shape = ()
            self._source_spacing = ()
            self._upload_needed = False
            self._initialized = False
            self._failed = False
            self._failure_reason = ""
            self._program = None
            self._quad_vbo = None
            self._texture_id = None
            self._mask_texture_id = None
            self._mask_data = None
            self._mask_shape = ()
            self._mask_cache_key = None
            self._mask_upload_needed = False
            self._texture_cache = OrderedDict()
            self._texture_cache_bytes = 0
            self._texture_cache_hits = 0
            self._texture_cache_misses = 0
            self._texture_cache_budget_bytes = _gpu_texture_cache_budget_bytes()
            self._preview_build_capabilities = GpuPreviewBuildCapabilities(reason="GPU preview build capability has not been probed")
            self._preview_texture_provider = None
            self._preview_stream_build_stats = {}
            self._transfer_lut_texture_id = None
            self._transfer_lut_data = build_volume_transfer_lut()
            self._transfer_lut_upload_needed = True
            self._mouse_mode = ""
            self._last_drag_pos = None
            self._cutoff = 0.35
            self._yaw = -35.0
            self._pitch = 20.0
            self._zoom = 1.0
            self._pan_x = 0.0
            self._pan_y = 0.0
            self._clarity_mode = False
            self._render_quality = 384
            self._sample_steps = 768
            self._inside_depth = 0.0
            self._front_clip = 0.0
            self._projection_mode = "composite"
            self._mask_mode = "image_only"
            self._mask_opacity = 0.45
            self._enhancement = 0.0
            self._tone_gamma = 1.0
            self._jitter_strength = 0.0
            self._adaptive_step_strength = 0.0
            self._gradient_opacity = 0.0
            self._gradient_opacity_range = (0.04, 0.34)
            self._surface_refine = False
            self._clip_plane_enabled = False
            self._clip_plane_depth = 0.0
            self._clip_plane_normal = (0.0, 0.0, 1.0)
            self._fast_interaction = False
            self._renderer_label = ""
            self._uploaded_shape = ()
            self._uploaded_bytes = 0
            self._last_upload_ms = 0.0
            self._last_draw_ms = 0.0
            self._last_steps = 0
            self._render_mode = "still"
            self._uploaded_dtype = ""
            self._transfer_preset = "amber"
            self._transfer_opacity = 1.0
            self.current_theme = "dark"
            self._clear_color_rgba = (*GPU_VOLUME_DARK_CLEAR_RGB, 1.0)

        def set_theme(self, theme):
            self.current_theme = normalize_theme(theme)
            rgb = GPU_VOLUME_LIGHT_CLEAR_RGB if self.current_theme == "light" else GPU_VOLUME_DARK_CLEAR_RGB
            self._clear_color_rgba = (float(rgb[0]), float(rgb[1]), float(rgb[2]), 1.0)
            self.update()

        def _apply_clear_color(self):
            red, green, blue, alpha = getattr(self, "_clear_color_rgba", (*GPU_VOLUME_DARK_CLEAR_RGB, 1.0))
            GL.glClearColor(float(red), float(green), float(blue), float(alpha))

        def setText(self, text):
            self._empty_text = str(text or "")
            self.update()

        def clear(self):
            self.clear_volume()

        def clear_volume(self):
            self._volume_data = None
            self._volume_shape = ()
            self._volume_cache_key = None
            self._source_shape = ()
            self._source_spacing = ()
            self._upload_needed = False
            if self._initialized and (self._texture_id or self._mask_texture_id or self._transfer_lut_texture_id):
                try:
                    self.makeCurrent()
                    self._release_texture_cache()
                    if self._texture_id:
                        GL.glDeleteTextures([int(self._texture_id)])
                    if self._mask_texture_id:
                        GL.glDeleteTextures([int(self._mask_texture_id)])
                        self._mask_texture_id = None
                    if self._transfer_lut_texture_id:
                        GL.glDeleteTextures([int(self._transfer_lut_texture_id)])
                        self._transfer_lut_texture_id = None
                        self._transfer_lut_upload_needed = True
                    self.doneCurrent()
                except Exception:
                    pass
            self._texture_id = None
            self._mask_data = None
            self._mask_shape = ()
            self._mask_cache_key = None
            self._mask_upload_needed = False
            self._uploaded_shape = ()
            self._uploaded_bytes = 0
            self._last_upload_ms = 0.0
            self._last_draw_ms = 0.0
            self._last_steps = 0
            self._uploaded_dtype = ""
            self._preview_texture_provider = None
            self._preview_stream_build_stats = {}
            self.update()

        def _delete_mask_texture(self):
            if self._initialized and self._mask_texture_id:
                try:
                    self.makeCurrent()
                    if not self._texture_id_is_cached(self._mask_texture_id):
                        GL.glDeleteTextures([int(self._mask_texture_id)])
                    self.doneCurrent()
                except Exception:
                    pass
            self._mask_texture_id = None

        _detach_mask_texture = _GpuVolumeRenderCore._detach_mask_texture
        _texture_cache_record_key = _GpuVolumeRenderCore._texture_cache_record_key
        _texture_cache_owner_from_key = _GpuVolumeRenderCore._texture_cache_owner_from_key
        _activate_cached_texture = _GpuVolumeRenderCore._activate_cached_texture
        _texture_cache_record_for_texture_id = _GpuVolumeRenderCore._texture_cache_record_for_texture_id
        _active_volume_texture_cache_bytes = _GpuVolumeRenderCore._active_volume_texture_cache_bytes
        _stream_build_texture_budget_bytes = _GpuVolumeRenderCore._stream_build_texture_budget_bytes
        set_stream_build_yield_callback = _GpuVolumeRenderCore.set_stream_build_yield_callback
        _reserve_texture_cache_bytes = _GpuVolumeRenderCore._reserve_texture_cache_bytes
        _texture_id_is_cached = _GpuVolumeRenderCore._texture_id_is_cached
        _new_upload_texture_id = _GpuVolumeRenderCore._new_upload_texture_id
        _remember_texture = _GpuVolumeRenderCore._remember_texture
        _prune_texture_cache = _GpuVolumeRenderCore._prune_texture_cache
        _texture_cache_eviction_candidate = _GpuVolumeRenderCore._texture_cache_eviction_candidate
        _release_texture_cache = _GpuVolumeRenderCore._release_texture_cache

        def has_volume(self):
            return (self._volume_data is not None or self._texture_id is not None) and not self._failed

        def release_texture_cache(self):
            if not self._initialized:
                return
            try:
                self.makeCurrent()
                self._release_texture_cache()
                self.doneCurrent()
                self.render_stats_changed.emit()
            except Exception:
                try:
                    self.doneCurrent()
                except Exception:
                    pass

        def set_volume_data(self, volume, source_shape=None, spacing_zyx=None, cache_key=None):
            if volume is None:
                self.clear_volume()
                return
            if cache_key is not None and self._activate_cached_texture(cache_key, "volume"):
                self._volume_cache_key = cache_key
                self._source_shape = tuple(int(value) for value in (source_shape or self._volume_shape))
                try:
                    next_spacing = tuple(float(value) for value in (spacing_zyx or ()))
                except (TypeError, ValueError):
                    next_spacing = ()
                self._source_spacing = next_spacing if len(next_spacing) == 3 and min(next_spacing) > 0 else ()
                self._volume_data = np.asarray(volume)
                self._upload_needed = False
                self._set_preview_texture_provider(
                    gpu_texture_preview_provider(
                        self._texture_id,
                        self._volume_shape,
                        self._uploaded_dtype,
                        source_shape=self._source_shape,
                        spacing_zyx=self._source_spacing,
                        cache_key=cache_key,
                        build_backend="gpu_cache",
                    )
                )
                self.update()
                return
            source = np.asarray(volume)
            if source.dtype == np.uint16:
                array = np.ascontiguousarray(source, dtype=np.uint16)
            else:
                array = np.ascontiguousarray(source, dtype=np.uint8)
            if array.ndim != 3 or min(array.shape) <= 0:
                self.clear_volume()
                return
            next_source_shape = tuple(int(value) for value in (source_shape or array.shape))
            if len(next_source_shape) != 3 or min(next_source_shape) <= 0:
                next_source_shape = tuple(int(value) for value in array.shape)
            try:
                next_spacing = tuple(float(value) for value in (spacing_zyx or ()))
            except (TypeError, ValueError):
                next_spacing = ()
            if len(next_spacing) != 3 or min(next_spacing) <= 0:
                next_spacing = ()
            if self._volume_data is not array:
                self._volume_data = array
                self._volume_shape = tuple(int(value) for value in array.shape)
                self._volume_cache_key = cache_key
                self._upload_needed = True
            else:
                self._volume_cache_key = cache_key
            self._source_shape = next_source_shape
            self._source_spacing = next_spacing
            self._set_preview_texture_provider(
                cpu_volume_preview_provider(
                    array,
                    source_shape=next_source_shape,
                    spacing_zyx=next_spacing,
                    cache_key=cache_key,
                    build_backend="cpu",
                )
            )
            if self._initialized and not self._failed:
                try:
                    self.makeCurrent()
                    self._upload_volume_if_needed()
                    self.doneCurrent()
                except Exception as exc:
                    self.doneCurrent()
                    self._mark_failed(f"GPU texture upload failed: {exc}")
            self.update()

        def build_volume_texture_from_source(self, volume, max_dim, algorithm="hybrid", preserve_source=False, cache_key=None, source_shape=None, spacing_zyx=None):
            if volume is None:
                self.clear_volume()
                return None
            try:
                if not self._initialized:
                    self.makeCurrent()
                    if not self._initialized:
                        self.initializeGL()
                else:
                    self.makeCurrent()
                provider = self._stream_upload_source_volume_texture(
                    volume,
                    max_dim,
                    algorithm=algorithm,
                    preserve_source=preserve_source,
                    cache_key=cache_key,
                    source_shape=source_shape,
                    spacing_zyx=spacing_zyx,
                )
                self.doneCurrent()
            except Exception as exc:
                try:
                    self.doneCurrent()
                except Exception:
                    pass
                self._mark_failed(f"GPU streamed preview build failed: {exc}")
                raise
            self.update()
            return provider

        _set_preview_texture_provider = _GpuVolumeRenderCore._set_preview_texture_provider
        _preview_provider_stats = _GpuVolumeRenderCore._preview_provider_stats

        def build_mask_texture_from_source(self, mask, max_dim, algorithm="occupancy", cache_key=None, source_shape=None):
            if mask is None:
                self.set_mask_data(None)
                return False
            try:
                if not self._initialized:
                    self.makeCurrent()
                    if not self._initialized:
                        self.initializeGL()
                else:
                    self.makeCurrent()
                result = self._stream_upload_source_mask_texture(
                    mask,
                    max_dim,
                    algorithm=algorithm,
                    cache_key=cache_key,
                    source_shape=source_shape,
                )
                self.doneCurrent()
            except Exception as exc:
                try:
                    self.doneCurrent()
                except Exception:
                    pass
                self._mark_failed(f"GPU streamed mask preview build failed: {exc}")
                raise
            self.update()
            return result

        def set_mask_data(self, mask, cache_key=None):
            if mask is None:
                self._detach_mask_texture()
                self._mask_data = None
                self._mask_shape = ()
                self._mask_cache_key = None
                self._mask_upload_needed = False
                self.update()
                return
            if cache_key is not None and self._activate_cached_texture(cache_key, "mask"):
                self._mask_cache_key = cache_key
                self._mask_data = np.asarray(mask)
                self._mask_upload_needed = False
                self.update()
                return
            source = np.asarray(mask)
            if source.ndim != 3 or min(source.shape) <= 0:
                self._detach_mask_texture()
                self._mask_data = None
                self._mask_shape = ()
                self._mask_cache_key = None
                self._mask_upload_needed = False
                self.update()
                return
            array = np.ascontiguousarray((source > 0).astype(np.uint8) * 255)
            if self._mask_data is None or self._mask_data.shape != array.shape or not np.array_equal(self._mask_data, array):
                self._mask_data = array
                self._mask_shape = tuple(int(value) for value in array.shape)
                self._mask_cache_key = cache_key
                self._mask_upload_needed = True
            else:
                self._mask_cache_key = cache_key
            if self._initialized and not self._failed:
                try:
                    self.makeCurrent()
                    self._upload_mask_if_needed()
                    self.doneCurrent()
                except Exception as exc:
                    self.doneCurrent()
                    self._mark_failed(f"GPU mask upload failed: {exc}")
            self.update()

        def set_render_state(
            self,
            cutoff_percent,
            yaw,
            pitch,
            zoom,
            render_quality,
            sample_steps=512,
            inside_depth=0.0,
            front_clip=0.0,
            render_mode="still",
            pan_x=0.0,
            pan_y=0.0,
            clarity_mode=False,
            projection_mode="composite",
            mask_mode="image_only",
            mask_opacity=0.45,
            supersample_scale=1.0,
            tint_rgb=(1.0, 0.83, 0.30),
            transfer_preset="amber",
            transfer_opacity=None,
            enhancement=0.0,
            tone_gamma=1.0,
            jitter_strength=None,
            adaptive_step_strength=None,
            gradient_opacity=None,
            gradient_opacity_range=None,
            shader_quality_mode="preset",
            surface_refine=False,
            clip_plane_enabled=False,
            clip_plane_depth=0.0,
            clip_plane_normal=(0.0, 0.0, 1.0),
        ):
            self._cutoff = max(0.0, min(0.98, float(cutoff_percent) / 100.0))
            self._yaw = float(yaw)
            self._pitch = float(pitch)
            self._zoom = max(0.2, float(zoom))
            self._render_quality = max(128, min(GPU_VOLUME_MAX_TEXTURE_DIM, int(render_quality)))
            min_steps = 192 if str(render_mode) == "drag" and str(projection_mode or "").lower() == "composite" else 256
            self._sample_steps = max(min_steps, min(GPU_VOLUME_MAX_RAY_STEPS, int(sample_steps)))
            self._inside_depth = max(0.0, min(1.6, float(inside_depth)))
            self._front_clip = max(0.0, min(0.92, float(front_clip)))
            self._render_mode = "drag" if str(render_mode) == "drag" else "still"
            pan_limit = volume_pan_limit_for_zoom(self._zoom)
            self._pan_x = max(-pan_limit, min(pan_limit, float(pan_x)))
            self._pan_y = max(-pan_limit, min(pan_limit, float(pan_y)))
            self._clarity_mode = bool(clarity_mode)
            projection_mode = str(projection_mode or "composite").lower()
            self._projection_mode = projection_mode if projection_mode in GPU_VOLUME_RENDER_MODES else "composite"
            self._fast_interaction = self._render_mode == "drag" and self._projection_mode == "composite"
            mask_mode = str(mask_mode or "image_only").lower()
            if not self._mask_texture_id or not self._mask_shape:
                mask_mode = "image_only"
            self._mask_mode = mask_mode if mask_mode in GPU_VOLUME_MASK_MODES else "image_only"
            self._mask_opacity = max(0.0, min(1.0, float(mask_opacity)))
            self._enhancement = max(0.0, min(1.0, float(enhancement))) if self._render_mode == "still" else 0.0
            self._tone_gamma = max(0.65, min(1.35, float(tone_gamma)))
            self._surface_refine = bool(surface_refine) and self._render_mode == "still"
            self._clip_plane_enabled = bool(clip_plane_enabled)
            self._clip_plane_depth = max(0.0, min(1.0, float(clip_plane_depth)))
            try:
                normal = tuple(float(value) for value in clip_plane_normal)
            except (TypeError, ValueError):
                normal = (0.0, 0.0, 1.0)
            if len(normal) != 3:
                normal = (0.0, 0.0, 1.0)
            length = math.sqrt(sum(value * value for value in normal))
            if length <= 1e-6:
                normal = (0.0, 0.0, 1.0)
                length = 1.0
            self._clip_plane_normal = tuple(float(value) / length for value in normal)
            self._supersample_scale = max(1.0, min(4.0, float(supersample_scale)))
            try:
                tint = tuple(float(value) for value in tint_rgb)
            except (TypeError, ValueError):
                tint = (1.0, 0.83, 0.30)
            if len(tint) != 3:
                tint = (1.0, 0.83, 0.30)
            self._tint_rgb = tuple(max(0.0, min(1.0, value)) for value in tint)
            self._transfer_preset = str(transfer_preset or "amber").lower()
            if self._transfer_preset not in TRANSFER_PRESET_IDS:
                self._transfer_preset = "amber"
            fallback_quality = volume_shader_quality_settings(
                self._transfer_preset,
                self._render_mode,
                self._projection_mode,
                self._mask_mode,
                self._clip_plane_enabled,
                shader_quality_mode,
            )
            self._shader_quality_mode = str(fallback_quality["shader_quality_mode"])
            fallback_gradient_opacity = float(fallback_quality["gradient_opacity"])
            fallback_gradient_range = tuple(fallback_quality["gradient_opacity_range"])
            if gradient_opacity is None:
                next_gradient_opacity = fallback_gradient_opacity
            else:
                next_gradient_opacity = _coerce_unit_float(gradient_opacity, fallback_gradient_opacity) if self._render_mode == "still" else 0.0
            gradient_low, gradient_high = _coerce_gradient_range(gradient_opacity_range, fallback_gradient_range)
            self._gradient_opacity = next_gradient_opacity
            self._gradient_opacity_range = (gradient_low, gradient_high)
            if jitter_strength is None:
                next_jitter = float(fallback_quality["jitter_strength"])
            else:
                next_jitter = _coerce_unit_float(jitter_strength, float(fallback_quality["jitter_strength"])) if self._render_mode == "still" else 0.0
            self._jitter_strength = next_jitter
            fallback_adaptive = float(fallback_quality["adaptive_step_strength"])
            if adaptive_step_strength is None:
                next_adaptive = fallback_adaptive
            else:
                next_adaptive = _coerce_unit_float(adaptive_step_strength, fallback_adaptive)
            if (
                self._render_mode != "still"
                or self._projection_mode != "composite"
                or self._mask_mode != "image_only"
                or self._clip_plane_enabled
            ):
                next_adaptive = 0.0
            self._adaptive_step_strength = next_adaptive
            if transfer_opacity is None:
                next_opacity = 0.72 if self._clarity_mode and self._render_mode == "still" else (1.0 if self._render_mode == "still" else 0.82)
            else:
                next_opacity = max(0.0, min(1.4, float(transfer_opacity)))
            next_lut = build_volume_transfer_lut(
                self._transfer_preset,
                self._tint_rgb,
                cutoff=0.0,
                opacity=next_opacity,
                clarity=self._clarity_mode and self._render_mode == "still",
            )
            if self._transfer_lut_data is None or not np.array_equal(self._transfer_lut_data, next_lut):
                self._transfer_lut_data = next_lut
                self._transfer_lut_upload_needed = True
            self._transfer_opacity = float(next_opacity)
            self.update()

        def render_stats(self):
            return {
                "mode": self._render_mode,
                "shape_zyx": tuple(int(value) for value in self._uploaded_shape),
                "bytes": int(self._uploaded_bytes),
                "upload_ms": float(self._last_upload_ms),
                "draw_ms": float(self._last_draw_ms),
                "steps": int(self._last_steps),
                "dtype": self._uploaded_dtype,
                "clarity": bool(self._clarity_mode),
                "texture_filter": _texture_filter_name(self._clarity_mode, self._render_mode, self._clip_plane_enabled),
                "display_scaling": _display_scaling_name(self._clarity_mode, self._render_mode, self._clip_plane_enabled),
                "projection_mode": getattr(self, "_projection_mode", "composite"),
                "mask_mode": getattr(self, "_mask_mode", "image_only"),
                "mask_shape_zyx": tuple(int(value) for value in getattr(self, "_mask_shape", ())),
                "enhancement": float(getattr(self, "_enhancement", 0.0)),
                "tone_gamma": float(getattr(self, "_tone_gamma", 1.0)),
                "shader_quality_mode": str(getattr(self, "_shader_quality_mode", "preset")),
                "jitter_strength": float(getattr(self, "_jitter_strength", 0.0)),
                "adaptive_step_strength": float(getattr(self, "_adaptive_step_strength", 0.0)),
                "gradient_opacity": float(getattr(self, "_gradient_opacity", 0.0)),
                "gradient_opacity_range": tuple(float(value) for value in getattr(self, "_gradient_opacity_range", (0.04, 0.34))),
                "surface_refine": bool(getattr(self, "_surface_refine", False)),
                "clip_plane_enabled": bool(getattr(self, "_clip_plane_enabled", False)),
                "clip_plane_depth": float(getattr(self, "_clip_plane_depth", 0.0)),
                "clip_plane_normal": tuple(float(value) for value in getattr(self, "_clip_plane_normal", (0.0, 0.0, 1.0))),
                "supersample_scale": float(getattr(self, "_supersample_scale", 1.0)),
                "tint_rgb": tuple(float(value) for value in getattr(self, "_tint_rgb", (1.0, 0.83, 0.30))),
                "transfer_preset": getattr(self, "_transfer_preset", "amber"),
                "transfer_opacity": float(getattr(self, "_transfer_opacity", 1.0)),
                "transfer_lut": tuple(int(value) for value in getattr(self, "_transfer_lut_data", np.zeros((1, 0, 4), dtype=np.uint8)).shape),
                "texture_cache_entries": int(len(getattr(self, "_texture_cache", {}) or {})),
                "texture_cache_bytes": int(getattr(self, "_texture_cache_bytes", 0) or 0),
                "texture_cache_budget_bytes": int(getattr(self, "_texture_cache_budget_bytes", 0) or 0),
                "texture_cache_hits": int(getattr(self, "_texture_cache_hits", 0) or 0),
                "texture_cache_misses": int(getattr(self, "_texture_cache_misses", 0) or 0),
                "gpu_preview_build": self._preview_build_capabilities.to_stats(),
                "gpu_stream_build": dict(getattr(self, "_preview_stream_build_stats", {}) or {}),
                "preview_provider": self._preview_provider_stats(),
            }

        def initializeGL(self):
            self._initialized = True
            try:
                self._apply_clear_color()
                GL.glDisable(GL.GL_DEPTH_TEST)
                self._update_renderer_label()
                self._preview_build_capabilities = probe_gpu_preview_build_capabilities()
                self._program = _link_program(_VERTEX_SHADER, _FRAGMENT_SHADER)
                vertices = np.array([-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0], dtype=np.float32)
                self._quad_vbo = GL.glGenBuffers(1)
                GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._quad_vbo)
                GL.glBufferData(GL.GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL.GL_STATIC_DRAW)
                GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
                self._upload_volume_if_needed()
                self._upload_mask_if_needed()
                self._upload_transfer_lut_if_needed()
            except Exception as exc:
                self._mark_failed(f"GPU renderer initialization failed: {exc}")

        def _update_renderer_label(self):
            vendor = _decode_gl_string(GL.glGetString(GL.GL_VENDOR))
            renderer = _decode_gl_string(GL.glGetString(GL.GL_RENDERER))
            version = _decode_gl_string(GL.glGetString(GL.GL_VERSION))
            label = _compact_renderer_text(renderer or vendor)
            self._renderer_label = label
            details = " | ".join(part for part in (vendor, renderer, version) if part)
            QTimer.singleShot(0, lambda: self.render_info_changed.emit(details or label))

        def renderer_label(self):
            return self._renderer_label

        def _try_start_local_axis_endpoint_drag(self, event):
            if self.workbench is None or event.button() != Qt.LeftButton:
                return False
            handler = getattr(self.workbench, "start_local_axis_endpoint_drag", None)
            if not callable(handler):
                return False
            if not handler(event.position().x(), event.position().y()):
                return False
            self._mouse_mode = "local_axis_endpoint"
            self._last_drag_pos = event.position()
            event.accept()
            return True

        def resizeGL(self, width, height):
            GL.glViewport(0, 0, max(1, int(width)), max(1, int(height)))

        def paintGL(self):
            try:
                self._apply_clear_color()
                GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            except Exception as exc:
                self._mark_failed(f"GPU clear failed: {exc}")
                return
            if self._failed or self._texture_id is None or not self._volume_shape:
                return
            try:
                self._upload_volume_if_needed()
                self._draw_volume()
            except Exception as exc:
                self._mark_failed(f"GPU render failed: {exc}")
                return

        def _upload_volume_if_needed(self):
            if not self._upload_needed or self._volume_data is None:
                return
            depth, height, width = self._volume_shape
            self._texture_id = self._new_upload_texture_id("volume")
            GL.glBindTexture(GL.GL_TEXTURE_3D, self._texture_id)
            texture_filter = GL.GL_NEAREST if _crisp_sampling_enabled(self._clarity_mode, self._render_mode, self._clip_plane_enabled) else GL.GL_LINEAR
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MIN_FILTER, texture_filter)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MAG_FILTER, texture_filter)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_R, GL.GL_CLAMP_TO_EDGE)
            GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
            internal_format, upload_format, pixel_type, _texture_format_name = _volume_texture_format(self._volume_data.dtype)
            started = time.perf_counter()
            GL.glTexImage3D(
                GL.GL_TEXTURE_3D,
                0,
                internal_format,
                int(width),
                int(height),
                int(depth),
                0,
                upload_format,
                pixel_type,
                self._volume_data,
            )
            self._last_upload_ms = (time.perf_counter() - started) * 1000.0
            self._uploaded_shape = (int(depth), int(height), int(width))
            self._uploaded_bytes = int(self._volume_data.nbytes)
            self._uploaded_dtype = str(self._volume_data.dtype)
            self._remember_texture(
                self._volume_cache_key,
                "volume",
                self._texture_id,
                self._uploaded_shape,
                self._uploaded_dtype,
                self._uploaded_bytes,
            )
            GL.glBindTexture(GL.GL_TEXTURE_3D, 0)
            self._upload_needed = False
            QTimer.singleShot(0, self.render_stats_changed.emit)

        def _upload_mask_if_needed(self):
            if not self._mask_upload_needed or self._mask_data is None:
                return
            depth, height, width = self._mask_shape
            self._mask_texture_id = self._new_upload_texture_id("mask")
            GL.glActiveTexture(GL.GL_TEXTURE2)
            GL.glBindTexture(GL.GL_TEXTURE_3D, self._mask_texture_id)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_R, GL.GL_CLAMP_TO_EDGE)
            GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
            GL.glTexImage3D(
                GL.GL_TEXTURE_3D,
                0,
                GL.GL_LUMINANCE,
                int(width),
                int(height),
                int(depth),
                0,
                GL.GL_LUMINANCE,
                GL.GL_UNSIGNED_BYTE,
                self._mask_data,
            )
            self._remember_texture(
                self._mask_cache_key,
                "mask",
                self._mask_texture_id,
                self._mask_shape,
                "uint8",
                int(getattr(self._mask_data, "nbytes", 0) or 0),
            )
            GL.glBindTexture(GL.GL_TEXTURE_3D, 0)
            GL.glActiveTexture(GL.GL_TEXTURE0)
            self._mask_upload_needed = False

        def _upload_transfer_lut_if_needed(self):
            if not self._transfer_lut_upload_needed or self._transfer_lut_data is None:
                return
            if not self._transfer_lut_texture_id:
                self._transfer_lut_texture_id = GL.glGenTextures(1)
            lut = np.ascontiguousarray(self._transfer_lut_data, dtype=np.uint8)
            height, width = int(lut.shape[0]), int(lut.shape[1])
            GL.glActiveTexture(GL.GL_TEXTURE1)
            GL.glBindTexture(GL.GL_TEXTURE_2D, self._transfer_lut_texture_id)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
            GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
            GL.glTexImage2D(
                GL.GL_TEXTURE_2D,
                0,
                GL.GL_RGBA,
                width,
                height,
                0,
                GL.GL_RGBA,
                GL.GL_UNSIGNED_BYTE,
                lut,
            )
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
            GL.glActiveTexture(GL.GL_TEXTURE0)
            self._transfer_lut_upload_needed = False

        def _draw_volume(self):
            if not self._program or not self._quad_vbo or not self._texture_id:
                return
            self._upload_mask_if_needed()
            self._upload_transfer_lut_if_needed()
            GL.glUseProgram(self._program)
            GL.glActiveTexture(GL.GL_TEXTURE0)
            GL.glBindTexture(GL.GL_TEXTURE_3D, self._texture_id)
            texture_filter = GL.GL_NEAREST if _crisp_sampling_enabled(self._clarity_mode, self._render_mode, self._clip_plane_enabled) else GL.GL_LINEAR
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MIN_FILTER, texture_filter)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MAG_FILTER, texture_filter)
            self._set_uniform_int("u_volume", 0)
            GL.glActiveTexture(GL.GL_TEXTURE1)
            GL.glBindTexture(GL.GL_TEXTURE_2D, self._transfer_lut_texture_id)
            self._set_uniform_int("u_transfer_lut", 1)
            GL.glActiveTexture(GL.GL_TEXTURE2)
            mask_mode = self._mask_mode if self._mask_texture_id and self._mask_shape else "image_only"
            GL.glBindTexture(GL.GL_TEXTURE_3D, self._mask_texture_id or self._texture_id)
            self._set_uniform_int("u_mask", 2)
            GL.glActiveTexture(GL.GL_TEXTURE0)
            self._set_uniform_float("u_cutoff", self._cutoff)
            self._set_uniform_float("u_zoom", self._zoom)
            self._set_uniform_vec2("u_pan", self._pan_x, self._pan_y)
            self._set_uniform_float("u_front_clip", self._front_clip)
            self._set_uniform_int("u_projection_mode", GPU_VOLUME_RENDER_MODES.get(getattr(self, "_projection_mode", "composite"), 0))
            self._set_uniform_int("u_mask_mode", GPU_VOLUME_MASK_MODES.get(mask_mode, 0))
            self._set_uniform_float("u_mask_opacity", self._mask_opacity)
            clarity = 1.0 if self._clarity_mode and self._render_mode == "still" else 0.0
            self._set_uniform_float("u_clarity", clarity)
            self._set_uniform_float("u_enhancement", self._enhancement)
            self._set_uniform_float("u_tone_gamma", self._tone_gamma)
            self._set_uniform_float("u_jitter_strength", self._jitter_strength)
            self._set_uniform_float("u_adaptive_step_strength", self._adaptive_step_strength)
            self._set_uniform_float("u_gradient_opacity", self._gradient_opacity)
            self._set_uniform_vec2("u_gradient_opacity_range", *self._gradient_opacity_range)
            self._set_uniform_vec3("u_tint_rgb", *self._tint_rgb)
            self._set_uniform_int("u_surface_refine", 1 if self._surface_refine else 0)
            self._set_uniform_int("u_fast_interaction", 1 if self._fast_interaction else 0)
            self._set_uniform_int("u_clip_plane_enabled", 1 if self._clip_plane_enabled else 0)
            self._set_uniform_float("u_clip_plane_depth", self._clip_plane_depth)
            self._set_uniform_vec3("u_clip_plane_normal", *self._clip_plane_normal)
            self._set_uniform_float("u_opacity", max(0.0, min(1.4, float(getattr(self, "_transfer_opacity", 1.0)))))
            self._set_uniform_float("u_gradient_weight", 1.35 if clarity > 0.0 else (1.0 if self._render_mode == "still" else 0.72))
            min_steps = 192 if self._fast_interaction else 256
            steps = max(min_steps, min(GPU_VOLUME_MAX_RAY_STEPS, int(self._sample_steps)))
            self._last_steps = int(steps)
            self._set_uniform_int("u_steps", steps)
            self._set_uniform_float("u_step_size", 1.58 / float(steps))
            self._set_uniform_vec2("u_viewport", float(max(1, self.width())), float(max(1, self.height())))
            depth, height, width = self._volume_shape
            x_scale, y_scale, z_scale = volume_shape_scale(self._source_shape or self._volume_shape, self._source_spacing)
            self._set_uniform_vec3("u_shape_scale", x_scale, y_scale, z_scale)
            self._set_uniform_vec3("u_texel_step", 1.0 / max(float(width), 1.0), 1.0 / max(float(height), 1.0), 1.0 / max(float(depth), 1.0))
            inv_rotation = _rotation_inverse_matrix(self._yaw, self._pitch)
            camera_distance = camera_distance_for_inside_zoom((x_scale, y_scale, z_scale), inv_rotation, self._zoom, self._inside_depth)
            self._set_uniform_float("u_camera_distance", camera_distance)
            loc = GL.glGetUniformLocation(self._program, "u_inv_rotation")
            if loc >= 0:
                GL.glUniformMatrix3fv(loc, 1, GL.GL_TRUE, inv_rotation)

            attr = GL.glGetAttribLocation(self._program, "a_position")
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self._quad_vbo)
            GL.glEnableVertexAttribArray(attr)
            GL.glVertexAttribPointer(attr, 2, GL.GL_FLOAT, False, 0, None)
            started = time.perf_counter()
            GL.glDrawArrays(GL.GL_TRIANGLE_STRIP, 0, 4)
            GL.glFlush()
            self._last_draw_ms = (time.perf_counter() - started) * 1000.0
            GL.glDisableVertexAttribArray(attr)
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
            GL.glBindTexture(GL.GL_TEXTURE_3D, 0)
            GL.glActiveTexture(GL.GL_TEXTURE1)
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
            GL.glActiveTexture(GL.GL_TEXTURE2)
            GL.glBindTexture(GL.GL_TEXTURE_3D, 0)
            GL.glActiveTexture(GL.GL_TEXTURE0)
            GL.glUseProgram(0)
            QTimer.singleShot(0, self.render_stats_changed.emit)

        def _set_uniform_float(self, name, value):
            loc = GL.glGetUniformLocation(self._program, name)
            if loc >= 0:
                GL.glUniform1f(loc, float(value))

        def _set_uniform_int(self, name, value):
            loc = GL.glGetUniformLocation(self._program, name)
            if loc >= 0:
                GL.glUniform1i(loc, int(value))

        def _set_uniform_vec2(self, name, x, y):
            loc = GL.glGetUniformLocation(self._program, name)
            if loc >= 0:
                GL.glUniform2f(loc, float(x), float(y))

        def _set_uniform_vec3(self, name, x, y, z):
            loc = GL.glGetUniformLocation(self._program, name)
            if loc >= 0:
                GL.glUniform3f(loc, float(x), float(y), float(z))

        def _mark_failed(self, reason):
            if self._failed:
                return
            self._failed = True
            self._failure_reason = str(reason or "GPU volume renderer failed")
            QTimer.singleShot(0, lambda: self.render_failed.emit(self._failure_reason))
            self.update()

        def mousePressEvent(self, event):
            self.setFocus(Qt.MouseFocusReason)
            if self.workbench is not None and event.button() == Qt.LeftButton:
                picker = getattr(self.workbench, "pick_local_axis_roll_reference_at", None)
                if callable(picker) and picker(event.position().x(), event.position().y()):
                    event.accept()
                    return
            if self._try_start_local_axis_endpoint_drag(event):
                return
            if self.workbench is not None and event.button() in (Qt.LeftButton, Qt.RightButton):
                self._mouse_mode = "rotate" if event.button() == Qt.LeftButton else "pan"
                self._last_drag_pos = event.position()
                event.accept()
                return
            super().mousePressEvent(event)

        def mouseMoveEvent(self, event):
            buttons = event.buttons()
            active = (
                (self._mouse_mode == "rotate" and buttons & Qt.LeftButton)
                or (self._mouse_mode == "local_axis_endpoint" and buttons & Qt.LeftButton)
                or (self._mouse_mode == "pan" and buttons & Qt.RightButton)
            )
            if self.workbench is not None and active and self._last_drag_pos is not None:
                current = event.position()
                dx = current.x() - self._last_drag_pos.x()
                dy = current.y() - self._last_drag_pos.y()
                self._last_drag_pos = current
                if self._mouse_mode == "local_axis_endpoint":
                    self.workbench.drag_local_axis_endpoint(current.x(), current.y())
                elif self._mouse_mode == "pan":
                    self.workbench.pan_volume_preview(dx, dy)
                else:
                    self.workbench.rotate_volume_preview(dx, dy)
                event.accept()
                return
            super().mouseMoveEvent(event)

        def mouseReleaseEvent(self, event):
            if event.button() in (Qt.LeftButton, Qt.RightButton) and self._mouse_mode:
                if self._mouse_mode == "local_axis_endpoint" and self.workbench is not None:
                    self.workbench.finish_local_axis_endpoint_drag()
                self._mouse_mode = ""
                self._last_drag_pos = None
                if self.workbench is not None:
                    self.workbench.finish_volume_interaction_debounced()
                event.accept()
                return
            super().mouseReleaseEvent(event)

        def wheelEvent(self, event):
            if self.workbench is None:
                event.ignore()
                return
            delta = event.angleDelta().y()
            if delta == 0:
                event.ignore()
                return
            self.workbench.zoom_volume_preview(1 if delta > 0 else -1)
            event.accept()

        def release_gl_resources(self):
            if not self._initialized:
                return
            try:
                self.makeCurrent()
            except Exception:
                return
            try:
                if hasattr(self, "_release_texture_cache"):
                    self._release_texture_cache()
                if self._texture_id:
                    GL.glDeleteTextures([int(self._texture_id)])
                    self._texture_id = None
                if self._mask_texture_id:
                    GL.glDeleteTextures([int(self._mask_texture_id)])
                    self._mask_texture_id = None
                if self._transfer_lut_texture_id:
                    GL.glDeleteTextures([int(self._transfer_lut_texture_id)])
                    self._transfer_lut_texture_id = None
                if self._quad_vbo:
                    GL.glDeleteBuffers(1, [int(self._quad_vbo)])
                    self._quad_vbo = None
                if self._program:
                    GL.glDeleteProgram(self._program)
                    self._program = None
                GL.glBindTexture(GL.GL_TEXTURE_3D, 0)
                GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
                GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
                GL.glUseProgram(0)
                GL.glFinish()
            finally:
                try:
                    self.doneCurrent()
                except Exception:
                    pass

        def delete_texture(self):
            self.release_gl_resources()

        def closeEvent(self, event):
            self.release_gl_resources()
            super().closeEvent(event)

else:
    TifGpuVolumeCanvas = None


__all__ = [
    "TifGpuVolumeCanvas",
    "TifGpuVolumeOffscreenRenderer",
    "TifGpuVolumeOffscreenWidget",
    "GPU_VOLUME_MAX_TEXTURE_DIM",
    "GPU_VOLUME_MAX_RAY_STEPS",
    "GPU_VOLUME_TRANSFER_LUT_SIZE",
    "GPU_VOLUME_MASK_MODES",
    "GPU_VOLUME_RENDER_MODES",
    "GPU_PREVIEW_BUILD_BACKEND_UNAVAILABLE",
    "GPU_PREVIEW_BUILD_BACKEND_FRAGMENT",
    "GPU_PREVIEW_BUILD_BACKEND_COMPUTE",
    "GpuPreviewBuildCapabilities",
    "VolumePreviewTextureProvider",
    "build_volume_transfer_lut",
    "cpu_volume_preview_provider",
    "gpu_texture_preview_provider",
    "probe_gpu_preview_build_capabilities",
    "gpu_volume_canvas_available",
    "gpu_volume_offscreen_available",
    "gpu_volume_unavailable_reason",
    "camera_distance_for_inside_zoom",
    "front_clip_start_t",
    "volume_shader_quality_settings",
    "volume_shape_scale",
]
