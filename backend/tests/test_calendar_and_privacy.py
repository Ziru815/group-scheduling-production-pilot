from app.schemas import ParticipantPublic, RankedCombination


def test_participant_public_dto_has_no_email_or_location():
    assert "email" not in ParticipantPublic.model_fields
    assert "location_input" not in ParticipantPublic.model_fields


def test_ranked_result_has_no_private_origin_or_credentials():
    fields = RankedCombination.model_fields
    assert "location_input" not in fields
    assert "credential_reference" not in fields
    assert "provider_user_id" not in fields

