"""Validate required moderation reasons before products are deactivated."""

from django import forms

from .models import ProductRemovalLog


class ProductRemovalForm(forms.ModelForm):
    """Collect only a reason while product and administrator stay server-controlled."""

    class Meta:
        """Expose the required explanation but no protected relationship fields."""

        # product, removed_by, and removed_at are assigned by trusted server code.
        model = ProductRemovalLog
        fields = ("reason",)
        widgets = {
            "reason": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Explain the policy or quality concern",
                }
            )
        }

    def clean_reason(self):
        """Reject vague or whitespace-only moderation explanations."""

        # strip normalizes accidental whitespace before storing the audit reason.
        reason = self.cleaned_data["reason"].strip()

        if len(reason) < 10:
            # A useful moderation log needs more context than a one-word label.
            raise forms.ValidationError("Please provide at least 10 characters.")

        return reason
