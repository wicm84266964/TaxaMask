"""Optional OpenGL ray-marched canvas for TIF volume preview."""

from __future__ import annotations

import math
import os
import time

os.environ.setdefault("__NV_PRIME_RENDER_OFFLOAD", "1")
os.environ.setdefault("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
os.environ.setdefault("QT_OPENGL", "desktop")

import numpy as np

GPU_VOLUME_MAX_TEXTURE_DIM = 4096
GPU_VOLUME_MAX_RAY_STEPS = 4096

try:
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
except Exception as exc:  # pragma: no cover - exercised only on partial Qt installs
    QOpenGLWidget = None
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
uniform vec3 u_texel_step;
uniform int u_steps;

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

    vec2 hit = intersect_box(ray_origin, ray_direction, half_size);
    if (hit.x > hit.y || hit.y < 0.0) {
        gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }

    float ray_start = max(hit.x, 0.0);
    float ray_end = hit.y;
    float t = mix(ray_start, ray_end, clamp(u_front_clip, 0.0, 0.92));
    vec4 accum = vec4(0.0);
    float first_depth = 0.0;
    float got_first_hit = 0.0;
    vec3 texel_step = max(u_texel_step, vec3(0.0005));
    vec3 light_dir = normalize(vec3(0.45, 0.58, 0.68));
    vec3 view_dir = normalize(-ray_direction);

    for (int i = 0; i < MAX_RAY_STEPS; ++i) {
        if (i >= u_steps || t > hit.y) {
            break;
        }
        vec3 point = ray_origin + ray_direction * t;
        vec3 texcoord = point / u_shape_scale + 0.5;
        float sample_value = texture3D(u_volume, texcoord).r;
        float density = clamp((sample_value - u_cutoff) / max(1.0 - u_cutoff, 0.001), 0.0, 1.0);
        if (density > 0.001) {
            float vx = texture3D(u_volume, texcoord + vec3(texel_step.x, 0.0, 0.0)).r -
                       texture3D(u_volume, texcoord - vec3(texel_step.x, 0.0, 0.0)).r;
            float vy = texture3D(u_volume, texcoord + vec3(0.0, texel_step.y, 0.0)).r -
                       texture3D(u_volume, texcoord - vec3(0.0, texel_step.y, 0.0)).r;
            float vz = texture3D(u_volume, texcoord + vec3(0.0, 0.0, texel_step.z)).r -
                       texture3D(u_volume, texcoord - vec3(0.0, 0.0, texel_step.z)).r;
            vec3 grad = vec3(vx, vy, vz);
            float grad_mag = clamp(length(grad) * 6.5, 0.0, 1.0);
            vec3 normal = normalize(grad + vec3(0.0001));
            float diffuse = max(dot(normal, light_dir), 0.0);
            float rim = pow(1.0 - max(dot(normal, view_dir), 0.0), 2.0);
            float spec = pow(max(dot(reflect(-light_dir, normal), view_dir), 0.0), 24.0);

            float soft_tissue = smoothstep(0.02, 0.36, density);
            float dense_tissue = smoothstep(0.34, 0.92, density);
            vec3 low_color = vec3(0.15, 0.45, 0.78);
            vec3 mid_color = vec3(0.62, 0.88, 0.95);
            vec3 high_color = vec3(1.0, 0.86, 0.54);
            vec3 transfer_color = mix(low_color, mid_color, soft_tissue);
            transfer_color = mix(transfer_color, high_color, dense_tissue);

            float surface = smoothstep(0.05, 0.35, grad_mag) * u_gradient_weight;
            float normal_opacity = pow(density, 1.22) * 18.0 + surface * pow(density, 0.55) * 24.0;
            float clarity_opacity = pow(density, 1.55) * 9.0 + surface * pow(density, 0.70) * 14.0;
            float opacity_density = mix(normal_opacity, clarity_opacity, clamp(u_clarity, 0.0, 1.0));
            float alpha = 1.0 - exp(-opacity_density * u_opacity * u_step_size);
            alpha = clamp(alpha, 0.0, mix(0.82, 0.46, clamp(u_clarity, 0.0, 1.0)));
            vec3 shaded = transfer_color * (0.50 + 0.42 * diffuse) + transfer_color * rim * mix(0.14, 0.22, u_clarity) + vec3(spec * mix(0.28, 0.42, u_clarity));

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

    if (accum.a <= 0.001) {
        gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }
    vec3 color = accum.rgb / max(accum.a, 0.001);
    color *= 0.78 + 0.22 * first_depth;
    color = pow(clamp(color, 0.0, 1.0), vec3(0.86));
    gl_FragColor = vec4(color, 1.0);
}
""".replace("__MAX_RAY_STEPS__", str(GPU_VOLUME_MAX_RAY_STEPS))


def gpu_volume_canvas_available():
    """Return True when the optional Qt/OpenGL imports needed by the canvas exist."""
    return QOpenGLWidget is not None and GL is not None


def gpu_volume_unavailable_reason():
    if QOpenGLWidget is None:
        return f"Qt OpenGL widget is unavailable: {_QT_OPENGL_IMPORT_ERROR}"
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
            self._source_shape = ()
            self._source_spacing = ()
            self._upload_needed = False
            self._initialized = False
            self._failed = False
            self._failure_reason = ""
            self._program = None
            self._quad_vbo = None
            self._texture_id = None
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
            self._renderer_label = ""
            self._uploaded_shape = ()
            self._uploaded_bytes = 0
            self._last_upload_ms = 0.0
            self._last_draw_ms = 0.0
            self._last_steps = 0
            self._render_mode = "still"
            self._uploaded_dtype = ""

        def setText(self, text):
            self._empty_text = str(text or "")
            self.update()

        def clear(self):
            self.clear_volume()

        def clear_volume(self):
            self._volume_data = None
            self._volume_shape = ()
            self._source_shape = ()
            self._source_spacing = ()
            self._upload_needed = False
            if self._initialized and self._texture_id:
                try:
                    self.makeCurrent()
                    GL.glDeleteTextures([int(self._texture_id)])
                    self.doneCurrent()
                except Exception:
                    pass
            self._texture_id = None
            self._uploaded_shape = ()
            self._uploaded_bytes = 0
            self._last_upload_ms = 0.0
            self._last_draw_ms = 0.0
            self._last_steps = 0
            self._uploaded_dtype = ""
            self.update()

        def has_volume(self):
            return self._volume_data is not None and not self._failed

        def set_volume_data(self, volume, source_shape=None, spacing_zyx=None):
            if volume is None:
                self.clear_volume()
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
                self._upload_needed = True
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
        ):
            self._cutoff = max(0.0, min(0.98, float(cutoff_percent) / 100.0))
            self._yaw = float(yaw)
            self._pitch = float(pitch)
            self._zoom = max(0.2, float(zoom))
            self._render_quality = max(128, min(GPU_VOLUME_MAX_TEXTURE_DIM, int(render_quality)))
            self._sample_steps = max(256, min(GPU_VOLUME_MAX_RAY_STEPS, int(sample_steps)))
            self._inside_depth = max(0.0, min(1.6, float(inside_depth)))
            self._front_clip = max(0.0, min(0.92, float(front_clip)))
            self._render_mode = "drag" if str(render_mode) == "drag" else "still"
            self._pan_x = max(-2.0, min(2.0, float(pan_x)))
            self._pan_y = max(-2.0, min(2.0, float(pan_y)))
            self._clarity_mode = bool(clarity_mode)
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
            if not self._texture_id:
                self._texture_id = GL.glGenTextures(1)
            GL.glBindTexture(GL.GL_TEXTURE_3D, self._texture_id)
            texture_filter = GL.GL_NEAREST if self._clarity_mode and self._render_mode == "still" else GL.GL_LINEAR
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
            GL.glBindTexture(GL.GL_TEXTURE_3D, 0)
            self._upload_needed = False
            QTimer.singleShot(0, self.render_stats_changed.emit)

        def _draw_volume(self):
            if not self._program or not self._quad_vbo or not self._texture_id:
                return
            GL.glUseProgram(self._program)
            GL.glActiveTexture(GL.GL_TEXTURE0)
            GL.glBindTexture(GL.GL_TEXTURE_3D, self._texture_id)
            texture_filter = GL.GL_NEAREST if self._clarity_mode and self._render_mode == "still" else GL.GL_LINEAR
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MIN_FILTER, texture_filter)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MAG_FILTER, texture_filter)
            self._set_uniform_int("u_volume", 0)
            self._set_uniform_float("u_cutoff", self._cutoff)
            self._set_uniform_float("u_zoom", self._zoom)
            self._set_uniform_vec2("u_pan", self._pan_x, self._pan_y)
            self._set_uniform_float("u_front_clip", self._front_clip)
            clarity = 1.0 if self._clarity_mode and self._render_mode == "still" else 0.0
            self._set_uniform_float("u_clarity", clarity)
            self._set_uniform_float("u_opacity", 0.72 if clarity > 0.0 else (1.0 if self._render_mode == "still" else 0.82))
            self._set_uniform_float("u_gradient_weight", 1.35 if clarity > 0.0 else (1.0 if self._render_mode == "still" else 0.72))
            steps = max(256, min(GPU_VOLUME_MAX_RAY_STEPS, int(self._sample_steps)))
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
                or (self._mouse_mode == "pan" and buttons & Qt.RightButton)
            )
            if self.workbench is not None and active and self._last_drag_pos is not None:
                current = event.position()
                dx = current.x() - self._last_drag_pos.x()
                dy = current.y() - self._last_drag_pos.y()
                self._last_drag_pos = current
                if self._mouse_mode == "pan":
                    self.workbench.pan_volume_preview(dx, dy)
                else:
                    self.workbench.rotate_volume_preview(dx, dy)
                event.accept()
                return
            super().mouseMoveEvent(event)

        def mouseReleaseEvent(self, event):
            if event.button() in (Qt.LeftButton, Qt.RightButton) and self._mouse_mode:
                self._mouse_mode = ""
                self._last_drag_pos = None
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
                if self._texture_id:
                    GL.glDeleteTextures([int(self._texture_id)])
                    self._texture_id = None
                if self._quad_vbo:
                    GL.glDeleteBuffers(1, [int(self._quad_vbo)])
                    self._quad_vbo = None
                if self._program:
                    GL.glDeleteProgram(self._program)
                    self._program = None
                GL.glBindTexture(GL.GL_TEXTURE_3D, 0)
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
    "GPU_VOLUME_MAX_TEXTURE_DIM",
    "GPU_VOLUME_MAX_RAY_STEPS",
    "gpu_volume_canvas_available",
    "gpu_volume_unavailable_reason",
    "camera_distance_for_inside_zoom",
    "front_clip_start_t",
    "volume_shape_scale",
]
