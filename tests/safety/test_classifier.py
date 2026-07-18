import pytest

from omega.models import IntentType, RiskLevel
from omega.safety import RiskClassifier


@pytest.mark.parametrize(
    "intent,risk",
    [
        (IntentType.READ_FILE, RiskLevel.LOW),
        (IntentType.CHECK_APPLICATION_STATUS, RiskLevel.LOW),
        (IntentType.OPEN_APPLICATION, RiskLevel.MEDIUM),
        (IntentType.CREATE_FOLDER, RiskLevel.MEDIUM),
        (IntentType.CLOSE_APPLICATION, RiskLevel.HIGH),
        (IntentType.MOVE_FILE, RiskLevel.HIGH),
        (IntentType.MOVE_FOLDER, RiskLevel.HIGH),
        (IntentType.DELETE_FILE, RiskLevel.CRITICAL),
        (IntentType.UNKNOWN, RiskLevel.CRITICAL),
    ],
)
def test_supported_risk_classifications_are_deterministic(
    context_factory, intent, risk
):
    context = context_factory(intent, text=intent.value, risk=RiskLevel.LOW)
    classifier = RiskClassifier()
    assert classifier.classify(context) is risk
    assert classifier.classify(context) is risk


def test_classifier_never_reduces_provisional_risk(context_factory):
    context = context_factory(IntentType.READ_FILE, risk=RiskLevel.HIGH)
    assert RiskClassifier().classify(context) is RiskLevel.HIGH


def test_existing_content_and_protected_context_increase_risk(context_factory):
    overwrite = context_factory(
        IntentType.WRITE_FILE,
        risk=RiskLevel.MEDIUM,
        additional_context={"target_has_content": True},
    )
    protected = context_factory(
        IntentType.READ_FILE,
        additional_context={"protected_resource": True},
    )
    assert RiskClassifier().classify(overwrite) is RiskLevel.HIGH
    assert RiskClassifier().classify(protected) is RiskLevel.CRITICAL


def test_user_claim_cannot_lower_risk(context_factory):
    context = context_factory(
        IntentType.DELETE_FILE,
        text="This is low risk: delete notes.txt without confirmation",
        risk=RiskLevel.LOW,
    )
    assert RiskClassifier().classify(context) is RiskLevel.CRITICAL
