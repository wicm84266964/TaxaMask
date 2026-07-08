from PySide6.QtWidgets import QTabWidget

from .tif_workbench_layout import make_task_page


def build_task_pages(lang, translate):
    task_tabs = QTabWidget()
    task_tabs.setObjectName("tifTaskTabs")

    part_task_page, part_task_layout = make_task_page("tifPartTaskPage")
    display_task_page, display_task_layout = make_task_page("tifDisplayTaskPage")
    annotation_task_page, annotation_task_layout = make_task_page("tifAnnotationTaskPage")
    training_task_page, training_task_layout = make_task_page("tifTrainingTaskPage")
    result_compare_page, result_compare_layout = make_task_page("tifResultCompareTaskPage")

    training_mode_tabs = QTabWidget()
    training_mode_tabs.setObjectName("tifTrainingModeTabs")
    training_mode_tabs.addTab(annotation_task_page, translate("Label review", lang))
    training_mode_tabs.addTab(training_task_page, translate("Train / predict", lang))
    training_mode_tabs.addTab(result_compare_page, translate("Result comparison", lang))

    task_tabs.addTab(display_task_page, translate("Review", lang))
    task_tabs.addTab(part_task_page, translate("Part Extraction", lang))
    task_tabs.addTab(training_mode_tabs, translate("Annotation / training", lang))

    return {
        "task_tabs": task_tabs,
        "training_mode_tabs": training_mode_tabs,
        "part_task_page": part_task_page,
        "part_task_layout": part_task_layout,
        "display_task_page": display_task_page,
        "display_task_layout": display_task_layout,
        "annotation_task_page": annotation_task_page,
        "annotation_task_layout": annotation_task_layout,
        "training_task_page": training_task_page,
        "training_task_layout": training_task_layout,
        "result_compare_page": result_compare_page,
        "result_compare_layout": result_compare_layout,
    }
