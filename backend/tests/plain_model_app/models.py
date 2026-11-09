from django.db import models


class Invoice(models.Model):
    """A business record that forgot to inherit OrgOwnedModel."""

    number = models.CharField(max_length=20)

    def __str__(self) -> str:
        return self.number
