from django.db.models import Q

class BaseFilter:
    """Base class for all filters."""
    def apply(self, qs, params):
        return qs


class SearchFilter(BaseFilter):
    def apply(self, qs, params):
        search = params.get("search")
        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(category__icontains=search)
            )
        return qs


class TypeFilter(BaseFilter):
    def apply(self, qs, params):
        types = params.get("types")
        if types:
            qs = qs.filter(type__in=types)
        return qs


class CategoryFilter(BaseFilter):
    def apply(self, qs, params):
        categories = params.get("categories")
        if categories:
            qs = qs.filter(category__in=categories)
        return qs


class DifficultyFilter(BaseFilter):
    def apply(self, qs, params):
        difficulty = params.get("difficulty")
        if difficulty and difficulty != "any":
            qs = qs.filter(difficulty__iexact=difficulty)
        return qs