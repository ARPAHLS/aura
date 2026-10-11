"""Tests for sequencer PII masking middleware, step op, and audit integration."""

from __future__ import annotations

import pytest

from aura.api import configure, agent
from aura.core.audit_report import AuditReportBuilder
from aura.core.constraints import ConstraintViolation
from aura.sequencer.middleware import MiddlewarePolicy, MiddlewareStack
from aura.sequencer.pii_mask import (
    NativePiiMasker,
    PiiMaskConfig,
    PiiMaskResult,
    PiiMasker,
    get_pii_provider,
    register_pii_provider,
)
from aura.sequencer.runner import SequencerRunner
from aura.sequencer.step import SequencerStep

# -------------------------------------------------------------------------
# Native Engine Unit Tests
# -------------------------------------------------------------------------


class TestNativePiiMasker:
    @pytest.fixture
    def masker(self) -> NativePiiMasker:
        return NativePiiMasker()

    def test_email_redact(self, masker: NativePiiMasker):
        text = "Contact alice.smith@example.org or bob@corp.co.uk for inquiries."
        cfg = PiiMaskConfig(strategy="redact")
        result = masker.mask_text(text, cfg)
        assert "[EMAIL]" in result.text
        assert "alice.smith@example.org" not in result.text
        assert "bob@corp.co.uk" not in result.text
        assert result.entity_counts.get("EMAIL") == 2
        assert result.redacted_count == 2

    def test_email_mask_strategy(self, masker: NativePiiMasker):
        text = "Send to customer@domain.com"
        cfg = PiiMaskConfig(strategy="mask")
        result = masker.mask_text(text, cfg)
        assert "@domain.com" in result.text
        assert "customer@domain.com" not in result.text
        assert "*" in result.text

    def test_email_pseudonymize_deterministic(self, masker: NativePiiMasker):
        text1 = "User alice@company.com logged in."
        text2 = "User alice@company.com made a payment."
        state: dict = {}
        cfg = PiiMaskConfig(strategy="pseudonymize")

        res1 = masker.mask_text(text1, cfg, session_state=state)
        res2 = masker.mask_text(text2, cfg, session_state=state)

        assert "<EMAIL_REF_" in res1.text
        # Both occurrences of the same email get the EXACT same pseudonym token
        token1 = [w for w in res1.text.split() if w.startswith("<EMAIL_REF_")][0]
        token2 = [w for w in res2.text.split() if w.startswith("<EMAIL_REF_")][0]
        assert token1 == token2

        # Different email gets a different token
        res3 = masker.mask_text("User bob@company.com called.", cfg, session_state=state)
        token3 = [w for w in res3.text.split() if w.startswith("<EMAIL_REF_")][0]
        assert token3 != token1

    def test_phone_number_redact(self, masker: NativePiiMasker):
        text = "Call +1-800-555-0199 or (555) 234-5678 immediately."
        cfg = PiiMaskConfig(strategy="redact")
        result = masker.mask_text(text, cfg)
        assert "[PHONE]" in result.text
        assert "+1-800-555-0199" not in result.text
        assert result.entity_counts.get("PHONE", 0) >= 1

    def test_phone_number_mask(self, masker: NativePiiMasker):
        text = "Direct line: 555-123-4567"
        cfg = PiiMaskConfig(strategy="mask")
        result = masker.mask_text(text, cfg)
        assert "4567" in result.text
        assert "*" in result.text

    def test_credit_card_luhn_valid(self, masker: NativePiiMasker):
        # 4532 0151 1284 3211 is a valid Visa test number (passes Luhn)
        valid_card = "4532-0151-1284-3211"
        text = f"Charged card {valid_card} $50"
        cfg = PiiMaskConfig(strategy="redact")
        result = masker.mask_text(text, cfg)
        assert "[CREDIT_CARD]" in result.text
        assert valid_card not in result.text
        assert result.entity_counts.get("CREDIT_CARD") == 1

    def test_credit_card_luhn_invalid_ignored(self, masker: NativePiiMasker):
        # 4532 0151 1284 3216 fails Luhn checksum — should NOT be masked as credit card
        invalid_card = "4532-0151-1284-3216"
        text = f"Serial number: {invalid_card}"
        cfg = PiiMaskConfig(strategy="redact", entities=["CREDIT_CARD"])
        result = masker.mask_text(text, cfg)
        assert "[CREDIT_CARD]" not in result.text
        assert invalid_card in result.text
        assert result.entity_counts.get("CREDIT_CARD", 0) == 0

    def test_credit_card_mask_strategy(self, masker: NativePiiMasker):
        valid_card = "4532015112843211"
        text = f"Card: {valid_card}"
        cfg = PiiMaskConfig(strategy="mask")
        result = masker.mask_text(text, cfg)
        assert "3211" in result.text
        assert "4532" not in result.text
        assert "*" in result.text

    def test_ssn_redact(self, masker: NativePiiMasker):
        text = "SSN: 123-45-6789 and 456-78-1234"
        cfg = PiiMaskConfig(strategy="redact")
        result = masker.mask_text(text, cfg)
        assert "[SSN]" in result.text
        assert "123-45-6789" not in result.text
        assert "456-78-1234" not in result.text
        assert result.entity_counts.get("SSN") == 2

    def test_ssn_invalid_ignored(self, masker: NativePiiMasker):
        # 000-xx-xxxx and 666-xx-xxxx are invalid SSNs
        text = "Invalid SSNs: 000-12-3456 and 666-12-3456"
        cfg = PiiMaskConfig(strategy="redact")
        result = masker.mask_text(text, cfg)
        assert result.entity_counts.get("SSN", 0) == 0
        assert "000-12-3456" in result.text

    def test_ip_address_redact(self, masker: NativePiiMasker):
        text = "Host 192.168.1.10 connected to 10.0.0.1"
        cfg = PiiMaskConfig(strategy="redact")
        result = masker.mask_text(text, cfg)
        assert "[IP_ADDRESS]" in result.text
        assert "192.168.1.10" not in result.text
        assert result.entity_counts.get("IP_ADDRESS") == 2

    def test_api_key_redact(self, masker: NativePiiMasker):
        text = "Using OpenAI key sk-abcdef1234567890abcdef123456 and AWS AKIAIOSFODNN7EXAMPLE"
        cfg = PiiMaskConfig(strategy="redact")
        result = masker.mask_text(text, cfg)
        assert "[API_KEY]" in result.text
        assert "sk-abcdef1234567890abcdef123456" not in result.text
        assert "AKIAIOSFODNN7EXAMPLE" not in result.text

    def test_jwt_redact(self, masker: NativePiiMasker):
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkFsaWNlIn0."
            "TJVA95OrM7E2cBab30RMHrHDcEfxjoYZgeFONFh7HgQ"
        )
        text = f"Authorization: Bearer {jwt}"
        cfg = PiiMaskConfig(strategy="redact")
        result = masker.mask_text(text, cfg)
        assert "[JWT]" in result.text or "[API_KEY]" in result.text
        assert jwt not in result.text

    def test_iban_redact(self, masker: NativePiiMasker):
        iban = "GB82WEST12345698765432"
        text = f"Transfer to IBAN {iban}"
        cfg = PiiMaskConfig(strategy="redact")
        result = masker.mask_text(text, cfg)
        assert "[IBAN]" in result.text
        assert iban not in result.text

    def test_allowlist_preservation(self, masker: NativePiiMasker):
        text = "Send alert to security@company.com and attacker@evil.org"
        cfg = PiiMaskConfig(
            strategy="redact",
            allowlist=["security@company.com"],
        )
        result = masker.mask_text(text, cfg)
        assert "security@company.com" in result.text
        assert "attacker@evil.org" not in result.text
        assert "[EMAIL]" in result.text
        assert result.redacted_count == 1

    def test_entity_filter_selective(self, masker: NativePiiMasker):
        text = "IP 192.168.1.1 and email user@test.com"
        # Only mask EMAIL, ignore IP_ADDRESS
        cfg = PiiMaskConfig(entities=["EMAIL"])
        result = masker.mask_text(text, cfg)
        assert "192.168.1.1" in result.text
        assert "user@test.com" not in result.text
        assert "[EMAIL]" in result.text


# -------------------------------------------------------------------------
# Coordinator Deep Traversal & Dot Path Filtering
# -------------------------------------------------------------------------


class TestPiiMaskerCoordinator:
    def test_nested_dict_and_list_masking(self):
        coordinator = PiiMasker()
        data = {
            "user": {
                "name": "John Doe",
                "email": "john.doe@test.com",
                "phones": ["555-0123", "555-0199"],
            },
            "meta": {
                "client_ip": "10.0.0.42",
                "counts": 5,
            },
        }
        res = coordinator.mask(data)
        assert res.redacted_count >= 3
        masked = res.data
        assert masked["user"]["email"] == "[EMAIL]"
        assert masked["meta"]["client_ip"] == "[IP_ADDRESS]"
        assert masked["meta"]["counts"] == 5

    def test_target_paths_filter(self):
        coordinator = PiiMasker()
        data = {
            "customer": {
                "email": "customer@secret.com",
            },
            "admin": {
                "email": "admin@secret.com",
            },
        }
        # Only mask customer.email, leave admin.email intact
        cfg = PiiMaskConfig(targets=["customer.email"])
        res = coordinator.mask(data, config=cfg)
        assert res.data["customer"]["email"] == "[EMAIL]"
        assert res.data["admin"]["email"] == "admin@secret.com"
        assert res.redacted_count == 1

    def test_strict_mode_raises_constraint_violation(self):
        coordinator = PiiMasker()
        data = {"leak": "my-secret@example.com"}
        cfg = PiiMaskConfig(strict=True)
        with pytest.raises(ConstraintViolation) as exc_info:
            coordinator.mask(data, config=cfg)
        assert "Strict PII policy violated" in str(exc_info.value)

    def test_custom_provider_protocol(self):
        class MockNerProvider:
            def mask_text(
                self,
                text: str,
                config: PiiMaskConfig,
                session_state: dict | None = None,
            ) -> PiiMaskResult:
                # Custom NER replacement
                new_text = text.replace("SecretProject", "[PROJECT_CODENAME]")
                count = 1 if "SecretProject" in text else 0
                return PiiMaskResult(
                    text=new_text,
                    redacted_count=count,
                    entity_counts={"PROJECT_CODENAME": count} if count else {},
                    modified_fields=["text"] if count else [],
                )

        register_pii_provider("ner_mock", MockNerProvider())
        assert get_pii_provider("ner_mock") is not None

        coordinator = PiiMasker()
        cfg = PiiMaskConfig(provider="ner_mock")
        res = coordinator.mask("Classified info on SecretProject", config=cfg)
        assert "[PROJECT_CODENAME]" in res.data
        assert res.redacted_count == 1


# -------------------------------------------------------------------------
# Sequencer Pipeline Step Op Integration (type: op, ref: middleware.pii_mask)
# -------------------------------------------------------------------------


class TestSequencerStepOp:
    def test_explicit_pii_mask_step_op(self, tmp_path):
        configure(home=tmp_path)
        a = agent("test-pii-op", create=True)

        steps = [
            SequencerStep(
                id="fetch_user",
                step_type="op",
                ref="echo",
                config={"email": "alice@domain.com", "ssn": "123-45-6789"},
            ),
            SequencerStep(
                id="sanitize_user",
                step_type="op",
                ref="middleware.pii_mask",
                config={
                    "source_step": "fetch_user",
                    "strategy": "redact",
                },
            ),
        ]

        with a.session() as s:
            runner = SequencerRunner(steps=steps)
            result = runner.run(s)
            assert result["success"] is True

            # Sanitize step output should have masked email and ssn
            sanitized = s.state["steps"]["sanitize_user"]["result"]
            assert sanitized["email"] == "[EMAIL]"
            assert sanitized["ssn"] == "[SSN]"

            # Check spine events
            events = s.get_events()
            pii_events = [e for e in events if e.kind == "middleware.applied"]
            assert len(pii_events) == 1
            payload = pii_events[0].payload
            assert payload["middleware"] == "middleware.pii_mask"
            assert payload["redacted_count"] == 2
            assert payload["strategy"] == "redact"
            # Crucial: verify zero raw PII on spine
            assert "alice@domain.com" not in str(payload)
            assert "123-45-6789" not in str(payload)

    def test_pii_mask_pseudonym_across_pipeline_steps(self, tmp_path):
        configure(home=tmp_path)
        a = agent("test-pseudonym-pipeline", create=True)

        steps = [
            SequencerStep(
                id="input_a",
                step_type="op",
                ref="echo",
                config={"raw": "Contact support@service.com now"},
            ),
            SequencerStep(
                id="mask_a",
                step_type="op",
                ref="middleware.pii_mask",
                config={"source_step": "input_a", "strategy": "pseudonymize"},
            ),
            SequencerStep(
                id="input_b",
                step_type="op",
                ref="echo",
                config={"raw": "Reminder to support@service.com tomorrow"},
            ),
            SequencerStep(
                id="mask_b",
                step_type="op",
                ref="middleware.pii_mask",
                config={"source_step": "input_b", "strategy": "pseudonymize"},
            ),
        ]

        with a.session() as s:
            runner = SequencerRunner(steps=steps)
            result = runner.run(s)
            assert result["success"] is True

            out_a = s.state["steps"]["mask_a"]["result"]["raw"]
            out_b = s.state["steps"]["mask_b"]["result"]["raw"]

            token_a = [w for w in out_a.split() if w.startswith("<EMAIL_REF_")][0]
            token_b = [w for w in out_b.split() if w.startswith("<EMAIL_REF_")][0]
            assert token_a == token_b  # Consistent deterministic token across steps


# -------------------------------------------------------------------------
# Boundary Middleware Integration (MiddlewarePolicy / MiddlewareStack)
# -------------------------------------------------------------------------


class TestBoundaryMiddleware:
    def test_per_step_outbound_sanitization(self, tmp_path):
        configure(home=tmp_path)
        a = agent("test-middleware-boundary", create=True)

        steps = [
            SequencerStep(
                id="generate_data",
                step_type="op",
                ref="echo",
                config={"leak": "Call +1-555-0199 or card 4532-0151-1284-3211"},
            ),
        ]

        # Attach per-step outbound PII mask middleware
        policy = MiddlewarePolicy(
            middleware="middleware.pii_mask",
            scope="per_step",
            config={"strategy": "redact"},
        )
        stack = MiddlewareStack(policies=[policy])

        with a.session() as s:
            runner = SequencerRunner(steps=steps, middleware_stack=stack)
            result = runner.run(s)
            assert result["success"] is True

            step_res = s.state["steps"]["generate_data"]["result"]
            assert "+1-555-0199" not in step_res["leak"]
            assert "4532-0151-1284-3211" not in step_res["leak"]
            assert "[PHONE]" in step_res["leak"] or "[CREDIT_CARD]" in step_res["leak"]

            # Verify spine recorded middleware.applied
            applied = [e for e in s.get_events() if e.kind == "middleware.applied"]
            assert len(applied) >= 1
            assert applied[0].payload["scope"] == "per_step"

    def test_strict_boundary_middleware_halts_on_pii(self, tmp_path):
        configure(home=tmp_path)
        a = agent("test-strict-boundary", create=True)

        steps = [
            SequencerStep(
                id="step_with_pii",
                step_type="op",
                ref="echo",
                config={"email": "violation@unauthorized.org"},
            ),
        ]

        policy = MiddlewarePolicy(
            middleware="middleware.pii_mask",
            scope="per_step",
            config={"strict": True},
        )
        stack = MiddlewareStack(policies=[policy])

        with a.session() as s:
            runner = SequencerRunner(steps=steps, middleware_stack=stack)
            result = runner.run(s)
            assert result["success"] is False
            assert "Strict PII policy violated" in result["error"]


# -------------------------------------------------------------------------
# Audit Report & Conformance Scorecard Integration
# -------------------------------------------------------------------------


class TestAuditReportIntegration:
    def test_audit_report_records_pii_scorecard_and_finding(self, tmp_path):
        configure(home=tmp_path)
        a = agent("test-pii-audit", create=True)

        steps = [
            SequencerStep(
                id="process_customer",
                step_type="op",
                ref="echo",
                config={"customer_email": "vip@enterprise.com", "ip": "172.16.0.1"},
            ),
        ]

        policy = MiddlewarePolicy(
            middleware="middleware.pii_mask",
            scope="per_step",
            config={"strategy": "redact"},
        )
        stack = MiddlewareStack(policies=[policy])

        with a.session() as s:
            runner = SequencerRunner(steps=steps, middleware_stack=stack)
            runner.run(s)

            report = AuditReportBuilder.build(s.spine)

            # Scorecard verification
            scorecard = report.scorecard
            assert "middleware" in scorecard
            assert scorecard["middleware"]["applied"] >= 1
            assert scorecard["middleware"]["pii_redactions"] >= 2

            # Finding verification
            pii_finding = next((f for f in report.findings if f.get("code") == "PII_MASKED"), None)
            assert pii_finding is not None
            assert pii_finding["severity"] == "info"
            assert pii_finding["redactions"] >= 2

            # Recommendation verification
            assert any("middleware.pii_mask" in r for r in report.recommendations)

            # Informational finding does not downgrade passing run
            assert report.verdict == "pass"

    def test_international_phone_coverage(self):
        masker = NativePiiMasker()
        cfg_redact = PiiMaskConfig(strategy="redact")
        cfg_mask = PiiMaskConfig(strategy="mask")

        # Global test vectors
        vectors = [
            ("+44 7911 123456", "UK international with space"),
            ("+447911123456", "UK compact E.164"),
            ("07911 123456", "UK national mobile"),
            ("+33 1 42 68 55 55", "France landline"),
            ("+49 (0)30 1234567", "Germany trunk prefix"),
            ("+30 210 1234567", "Greece Athens"),
            ("+81 3 1234 5678", "Japan Tokyo"),
            ("+91 98765 43210", "India mobile"),
        ]

        for phone_raw, label in vectors:
            text = f"Customer phone ({label}): {phone_raw}"
            res_redact = masker.mask_text(text, cfg_redact)
            assert "[PHONE]" in res_redact.text, f"Failed redact on {label}: {phone_raw}"
            assert phone_raw not in res_redact.text

            res_mask = masker.mask_text(text, cfg_mask)
            assert "***" in res_mask.text, f"Failed mask on {label}: {phone_raw}"

    def test_callable_custom_provider_and_alias_lookup(self):
        # Callable custom provider (e.g., simulating ARPA micro-f1-mask or Skillware)
        def custom_ner(text: str, cfg: PiiMaskConfig, session_state: dict | None = None):
            if "PROJECT_CODENAME_ALPHA" in text:
                return text.replace("PROJECT_CODENAME_ALPHA", "[SECRET_PROJECT]"), {
                    "project_ner": 1
                }
            return text, {}

        register_pii_provider("micro-f1-mask", custom_ner)

        # Lookup with hyphen or underscore
        prov_hyphen = get_pii_provider("micro-f1-mask")
        prov_underscore = get_pii_provider("micro_f1_mask")
        assert prov_hyphen is prov_underscore

        # Masking through PiiMasker with custom provider in config
        masker = PiiMasker()
        cfg = PiiMaskConfig(provider="micro-f1-mask")
        data = {"mission": "Top secret PROJECT_CODENAME_ALPHA deployment"}
        res = masker.mask(data, cfg)
        assert res.data["mission"] == "Top secret [SECRET_PROJECT] deployment"
        assert res.entities_detected.get("project_ner") == 1
        assert res.total_redactions == 1

    def test_provider_fault_tolerance_on_error(self):
        def crashing_provider(text: str, cfg: PiiMaskConfig, session_state: dict | None = None):
            raise RuntimeError("Model service timeout")

        # 1. Fallback mode (default): gracefully falls back to Tier 1 native engine
        masker_fallback = PiiMasker(provider=crashing_provider)
        cfg_fallback = PiiMaskConfig(on_error="fallback")
        res_fb = masker_fallback.mask(
            {"contact": "reach out at admin@corp.com"},
            cfg_fallback,
        )
        assert "[EMAIL]" in res_fb.data["contact"]
        assert "admin@corp.com" not in res_fb.data["contact"]

        # 2. Fail mode: raises error
        cfg_fail = PiiMaskConfig(on_error="fail")
        with pytest.raises(RuntimeError, match="Model service timeout"):
            masker_fallback.mask("admin@corp.com", cfg_fail)

        # 3. Pass mode: returns raw text untouched without crashing
        cfg_pass = PiiMaskConfig(on_error="pass")
        res_pass = masker_fallback.mask("admin@corp.com", cfg_pass)
        assert res_pass.data == "admin@corp.com"
