try:
    from .pdf_classifier import LLMScreenPDFClassifier
except ModuleNotFoundError:
    LLMScreenPDFClassifier = None

try:
    from .pdf_extractor import EnhancedPDFExtractionSystem
except ModuleNotFoundError:
    EnhancedPDFExtractionSystem = None

try:
    from .poppler_discovery import discover_poppler, poppler_path_for_pdf2image
except ModuleNotFoundError:
    discover_poppler = None
    poppler_path_for_pdf2image = None

try:
    from .multimodal_validator import MultimodalValidator, ValidationResult
except ModuleNotFoundError:
    MultimodalValidator = None
    ValidationResult = None
