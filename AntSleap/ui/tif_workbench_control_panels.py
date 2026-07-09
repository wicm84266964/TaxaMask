from .tif_workbench_layout import make_panel, make_section


def build_right_control_panel(title_registry=None, section_title_registry=None):
    panel, layout = make_panel("Volume controls", "tifControlPanel", title_registry)
    panel.setMinimumWidth(360)
    panel.setMaximumWidth(520)
    operation_status_section, operation_status_layout = make_section(
        "Recent operation",
        "tifOperationStatusSection",
        section_title_registry,
    )
    return {
        "panel": panel,
        "layout": layout,
        "operation_status_section": operation_status_section,
        "operation_status_layout": operation_status_layout,
    }
