"""Optional OpenGL ray-marched canvas for TIF volume preview."""

from __future__ import annotations

import math
import os
import time
from collections import OrderedDict

os.environ.setdefault("__NV_PRIME_RENDER_OFFLOAD", "1")
os.environ.setdefault("__GLX_VENDOR_LIBRARY_NAME", "nvidia")

import numpy as np

try:
    from AntSleap.core.tif_transfer_function import TRANSFER_PRESET_IDS, build_transfer_lut, normalize_transfer_function
except ModuleNotFoundError as exc:
    if exc.name != "AntSleap":
        raise
    from core.tif_transfer_function import TRANSFER_PRESET_IDS, build_transfer_lut, normalize_transfer_function

GPU_VOLUME_MAX_TEXTURE_DIM = 4096
GPU_VOLUME_MAX_RAY_STEPS = 4096
GPU_VOLUME_TRANSFER_LUT_SIZE = 256
GPU_VOLUME_TEXTURE_CACHE_DEFAULT_BUDGET_BYTES = 2 * 1024 * 1024 * 1024
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
        return True

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
        return self._volume_data is not None and not self._failed

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
        if self._mask_data is None:
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
        }

    def renderer_label(self):
        return self._renderer_label

    def render_scale(self):
        return float(self._supersample_scale)

    def renderer_details(self):
        return self._renderer_details or self._renderer_label

    def _initialize_render_core(self):
        GL.glClearColor(0.027, 0.035, 0.039, 1.0)
        GL.glDisable(GL.GL_DEPTH_TEST)
        self._update_renderer_label()
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
        if np.dtype(self._volume_data.dtype) == np.uint16:
            internal_format = GL.GL_LUMINANCE16
            pixel_type = GL.GL_UNSIGNED_SHORT
        else:
            internal_format = GL.GL_LUMINANCE
            pixel_type = GL.GL_UNSIGNED_BYTE
        started = time.perf_counter()
        GL.glTexImage3D(
            GL.GL_TEXTURE_3D,
            0,
            internal_format,
            int(width),
            int(height),
            int(depth),
            0,
            GL.GL_LUMINANCE,
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
        mask_mode = self._mask_mode if self._mask_texture_id and self._mask_data is not None else "image_only"
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

        def set_mask_data(self, mask, cache_key=None):
            return self._store_mask_data(mask, cache_key=cache_key)

        def render_image(self, width, height):
            display_width = max(1, int(width))
            display_height = max(1, int(height))
            scale = max(1.0, min(4.0, float(self.render_scale())))
            width = max(1, int(round(display_width * scale)))
            height = max(1, int(round(display_height * scale)))
            self.initialize()
            if self._failed or self._volume_data is None or not self._volume_shape:
                return None
            if not self._context.makeCurrent(self._surface):
                raise RuntimeError("OpenGL offscreen context makeCurrent failed")
            try:
                self._ensure_fbo(width, height)
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self._fbo)
                GL.glViewport(0, 0, width, height)
                GL.glClearColor(0.027, 0.035, 0.039, 1.0)
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

        def set_mask_data(self, mask, cache_key=None):
            try:
                self._renderer.set_mask_data(mask, cache_key=cache_key)
                self._request_render_to_label()
            except Exception as exc:
                self._mark_failed(f"GPU offscreen mask upload failed: {exc}")

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
                    painter.setBrush(QColor(7, 9, 10, 150))
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
                    painter.setBrush(QColor(7, 9, 10, 185))
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
            painter.fillRect(rect, QColor(7, 9, 10, 205))
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
        _texture_id_is_cached = _GpuVolumeRenderCore._texture_id_is_cached
        _new_upload_texture_id = _GpuVolumeRenderCore._new_upload_texture_id
        _remember_texture = _GpuVolumeRenderCore._remember_texture
        _prune_texture_cache = _GpuVolumeRenderCore._prune_texture_cache
        _texture_cache_eviction_candidate = _GpuVolumeRenderCore._texture_cache_eviction_candidate
        _release_texture_cache = _GpuVolumeRenderCore._release_texture_cache

        def has_volume(self):
            return self._volume_data is not None and not self._failed

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
            if self._initialized and not self._failed:
                try:
                    self.makeCurrent()
                    self._upload_volume_if_needed()
                    self.doneCurrent()
                except Exception as exc:
                    self.doneCurrent()
                    self._mark_failed(f"GPU texture upload failed: {exc}")
            self.update()

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
            if self._mask_data is None:
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
            }

        def initializeGL(self):
            self._initialized = True
            try:
                GL.glClearColor(0.027, 0.035, 0.039, 1.0)
                GL.glDisable(GL.GL_DEPTH_TEST)
                self._update_renderer_label()
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
                GL.glClearColor(0.027, 0.035, 0.039, 1.0)
                GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            except Exception as exc:
                self._mark_failed(f"GPU clear failed: {exc}")
                return
            if self._failed or self._volume_data is None or not self._volume_shape:
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
            if np.dtype(self._volume_data.dtype) == np.uint16:
                internal_format = GL.GL_LUMINANCE16
                pixel_type = GL.GL_UNSIGNED_SHORT
            else:
                internal_format = GL.GL_LUMINANCE
                pixel_type = GL.GL_UNSIGNED_BYTE
            started = time.perf_counter()
            GL.glTexImage3D(
                GL.GL_TEXTURE_3D,
                0,
                internal_format,
                int(width),
                int(height),
                int(depth),
                0,
                GL.GL_LUMINANCE,
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
            mask_mode = self._mask_mode if self._mask_texture_id and self._mask_data is not None else "image_only"
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
    "build_volume_transfer_lut",
    "gpu_volume_canvas_available",
    "gpu_volume_offscreen_available",
    "gpu_volume_unavailable_reason",
    "camera_distance_for_inside_zoom",
    "front_clip_start_t",
    "volume_shader_quality_settings",
    "volume_shape_scale",
]
