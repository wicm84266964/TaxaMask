"""Run nnU-Net prediction with TaxaMask-owned trainer classes available."""

import importlib


CUSTOM_TRAINERS = {
    "nnUNetTrainerTifBlink": (
        "tif_blink_nnunet.nnunet_trainer",
        "nnUNetTrainerTifBlink",
    ),
}


def resolve_custom_trainer(class_name):
    target = CUSTOM_TRAINERS.get(str(class_name or ""))
    if target is None:
        return None
    module_name, attribute_name = target
    module = importlib.import_module(module_name)
    trainer_class = getattr(module, attribute_name)
    if trainer_class.__name__ != class_name:
        raise RuntimeError(f"taxamask_trainer_name_mismatch:{class_name}")
    return trainer_class


def install_custom_trainer_resolver(prediction_module):
    current_resolver = prediction_module.recursive_find_python_class
    if getattr(current_resolver, "_taxamask_custom_trainer_resolver", False):
        return current_resolver

    def resolve(folder, class_name, current_module):
        custom_trainer = resolve_custom_trainer(class_name)
        if custom_trainer is not None:
            return custom_trainer
        return current_resolver(folder, class_name, current_module)

    resolve._taxamask_custom_trainer_resolver = True
    prediction_module.recursive_find_python_class = resolve
    return resolve


def main():
    from nnunetv2.inference import predict_from_raw_data

    install_custom_trainer_resolver(predict_from_raw_data)
    predict_from_raw_data.predict_entry_point()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
