def compute_centered_window_geometry(available_rect, desired_size, padding=32):
    """Return a screen-safe centered geometry tuple (x, y, width, height).

    available_rect: (left, top, width, height)
    desired_size: (width, height)
    padding: keep a small margin from screen edges when clamping
    """
    left, top, available_width, available_height = [int(v) for v in available_rect]
    desired_width, desired_height = [int(v) for v in desired_size]
    padding = max(0, int(padding))

    usable_width = max(1, available_width - padding)
    usable_height = max(1, available_height - padding)

    width = min(desired_width, usable_width, available_width)
    height = min(desired_height, usable_height, available_height)

    width = max(1, width)
    height = max(1, height)

    x = left + max(0, (available_width - width) // 2)
    y = top + max(0, (available_height - height) // 2)
    return x, y, width, height
