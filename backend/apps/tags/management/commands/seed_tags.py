from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.tags.models import Tag


SEEDS = [
    # mood
    ("mood", ["chill", "vent", "flirty", "philosophical", "late-night", "lonely", "wholesome", "hype"]),
    # topic
    ("topic", ["music", "gaming", "movies", "anime", "books", "tech", "art", "sports", "travel", "cooking"]),
    # spice
    ("spice", ["sfw", "spicy"]),
    # language
    ("language", ["english", "spanish", "french", "german", "hindi", "japanese"]),
    # region
    ("region", ["americas", "europe", "asia", "africa", "oceania"]),
    # time
    ("time", ["morning", "afternoon", "evening", "3am"]),
]


class Command(BaseCommand):
    help = "Seed the curated tag catalog."

    def handle(self, *args, **opts):
        created = 0
        for category, labels in SEEDS:
            for label in labels:
                slug = slugify(label)
                _, was_created = Tag.objects.get_or_create(
                    slug=slug, defaults={"label": label, "category": category}
                )
                created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Seeded ({created} new)."))
