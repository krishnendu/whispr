from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    tags = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "handle", "pronouns", "locale", "age_confirmed",
            "trust_score", "is_operator", "onboarding_complete", "tags",
        ]
        read_only_fields = ["id", "trust_score", "is_operator"]

    def get_tags(self, obj):
        return [
            {"slug": ut.tag.slug, "label": ut.tag.label, "category": ut.tag.category}
            for ut in obj.user_tags.select_related("tag").all()
        ]


class UpdateProfileSerializer(serializers.ModelSerializer):
    tag_slugs = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = User
        fields = ["handle", "pronouns", "locale", "age_confirmed", "tag_slugs"]

    def validate_handle(self, value):
        v = value.strip().lower()
        if not v or not all(c.isalnum() or c in "-_" for c in v):
            raise serializers.ValidationError("Handle must be alphanumeric, dashes or underscores.")
        if len(v) < 3 or len(v) > 32:
            raise serializers.ValidationError("Handle must be 3–32 characters.")
        qs = User.objects.filter(handle=v).exclude(pk=self.instance.pk if self.instance else None)
        if qs.exists():
            raise serializers.ValidationError("That handle is taken.")
        return v
