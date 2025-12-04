from abc import ABC, abstractmethod

class SortStrategy(ABC):
    @abstractmethod
    def sort(self, qs):
        pass


class NewestSort(SortStrategy):
    def sort(self, qs):
        return qs.order_by('-created_at')


class PopularSort(SortStrategy):
    def sort(self, qs):
        return qs.order_by('-views', '-rating')


class TitleSort(SortStrategy):
    def sort(self, qs):
        return qs.order_by('title')


class RecommendedSort(SortStrategy):
    def sort(self, qs):
        return qs.order_by('-featured', '-rating', '-created_at')


SORT_STRATEGIES = {
    'newest': NewestSort(),
    'popular': PopularSort(),
    'title': TitleSort(),
    'recommended': RecommendedSort(),
}