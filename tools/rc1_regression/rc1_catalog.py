"""Localización de la evidencia RC1 cerrada. No importa el motor."""

RC1_TAG = "v1.0.0-rc1"
RC1_REVISION = "86597493672d2ebd445993999e1940b5471222b2"
RC1_SOFTWARE_VERSION = "1.0.0-rc1"

# La sensibilidad se exporta solo como manifiesto completo. No hay official/.
PACKAGES = (
    {
        "family": "e1",
        "role": "official",
        "campaign_id": "e1-strategy-alessi-10k",
        "campaign_identity": "efe47dd9-61f4-50d5-a2ba-11144c800493",
        "package": "evidence/official/e1/efe47dd9-61f4-50d5-a2ba-11144c800493.json",
        "manifest": "evidence/manifests/efe47dd9-61f4-50d5-a2ba-11144c800493.json",
        "artifact_types": ("e1_configurable_bank_result",),
    },
    {
        "family": "e2",
        "role": "official",
        "campaign_id": "e2-offered-load",
        "campaign_identity": "d66bf23b-6392-5e01-b9c5-c0531c098d9d",
        "package": "evidence/official/e2/d66bf23b-6392-5e01-b9c5-c0531c098d9d.json",
        "manifest": "evidence/manifests/d66bf23b-6392-5e01-b9c5-c0531c098d9d.json",
        "artifact_types": ("e2_configurable_bank_result",),
    },
    {
        "family": "e3",
        "role": "official",
        "campaign_id": "e3-recovery-policy",
        "campaign_identity": "b0228a7c-cd9a-515a-b799-96aaed75841a",
        "package": "evidence/official/e3/b0228a7c-cd9a-515a-b799-96aaed75841a.json",
        "manifest": "evidence/manifests/b0228a7c-cd9a-515a-b799-96aaed75841a.json",
        "artifact_types": ("e3_configurable_bank_result",),
    },
    {
        "family": "e3_sensitivity",
        "role": "sensitivity",
        "campaign_id": "e3-loss-position-sensitivity",
        "campaign_identity": "05409804-725d-5f2d-9994-bac39ea41974",
        "package": "evidence/manifests/05409804-725d-5f2d-9994-bac39ea41974.json",
        "manifest": None,
        "artifact_types": ("e3_sensitivity_configurable_bank_result",),
    },
)

RUN_ORDER_FIELDS = (
    "index",
    "label",
    "configuration_hash",
    "dataset_fingerprint",
    "dataset_identity",
    "execution_identity",
    "completed",
    "failed",
)
