# from django.shortcuts import render
# from django.core.paginator import Paginator
# from django.db.models import Q
# from .models import Resources

# def resource_list(request):
#     qs = Resources.objects.all()

#     # --- Read query params ---
#     search = request.GET.get('search', '').strip()
#     types = request.GET.getlist('type')          # multi-select
#     categories = request.GET.getlist('category') # multi-select
#     difficulty = request.GET.get('difficulty', '')  # single
#     sort = request.GET.get('sort', 'recommended')
#     page = request.GET.get('page', 1)

#     # --- Filtering ---
#     if search:
#         # search across title, description, category
#         qs = qs.filter(
#             Q(title__icontains=search) |
#             Q(description__icontains=search) |
#             Q(category__icontains=search)
#         )

#     if types:
#         qs = qs.filter(type__in=types)

#     if categories:
#         qs = qs.filter(category__in=categories)

#     if difficulty and difficulty.lower() != 'any':
#         qs = qs.filter(difficulty__iexact=difficulty)

#     # --- Sorting ---
#     if sort == 'newest':
#         qs = qs.order_by('-created_at')
#     elif sort == 'popular':
#         # using views then rating
#         qs = qs.order_by('-views', '-rating')
#     elif sort == 'title':
#         qs = qs.order_by('title')
#     else:  # recommended (default)
#         # Featured first then rating then newest
#         qs = qs.order_by('-featured', '-rating', '-created_at')

#     # --- Pagination ---
#     ITEMS_PER_PAGE = 9
#     paginator = Paginator(qs, ITEMS_PER_PAGE)
#     page_obj = paginator.get_page(page)

#     # Useful context to maintain selected filters in the template
#     context = {
#         'page_obj': page_obj,
#         'resources': page_obj.object_list,
#         'total_resources': qs.count(),
#         'selected_search': search,
#         'selected_types': types,
#         'selected_categories': categories,
#         'selected_difficulty': difficulty or 'any',
#         'selected_sort': sort,
#         # If you want to list all categories/types in filter UI:
#         'all_types': [t[0] for t in Resources.TYPE_CHOICES],
#         # you might want to compute unique categories from DB:
#         'all_categories': Resources.objects.order_by().values_list('category', flat=True).distinct(),
#     }
#     return render(request, 'resources/resources.html', context)


from django.core.paginator import Paginator
from django.shortcuts import render

from .models import Resources
from .strategies.sorting import SORT_STRATEGIES, RecommendedSort
from .strategies.filtering import (
    SearchFilter, TypeFilter, CategoryFilter, DifficultyFilter
)
from .pipelines.filters_pipeline import FilterPipeline


def resource_list(request):
    qs = Resources.objects.all()

    # --- Gather query params ---
    params = {
        "search": request.GET.get("search", "").strip(),
        "types": request.GET.getlist("type"),
        "categories": request.GET.getlist("category"),
        "difficulty": request.GET.get("difficulty", "any"),
    }

    # --- Run Filter Pipeline ---
    filter_pipeline = FilterPipeline([
        SearchFilter(),
        TypeFilter(),
        CategoryFilter(),
        DifficultyFilter(),
    ])

    qs = filter_pipeline.run(qs, params)

    # --- Sorting using Strategy ---
    sort_key = request.GET.get("sort", "recommended")
    sorter = SORT_STRATEGIES.get(sort_key, RecommendedSort())
    qs = sorter.sort(qs)

    # --- Pagination ---
    paginator = Paginator(qs, 9)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    # --- Context ---
    context = {
        "page_obj": page_obj,
        "resources": page_obj.object_list,
        "total_resources": qs.count(),
        "selected_search": params["search"],
        "selected_types": params["types"],
        "selected_categories": params["categories"],
        "selected_difficulty": params["difficulty"],
        "selected_sort": sort_key,
        "all_types": [t[0] for t in Resources.TYPE_CHOICES],
        "all_categories": Resources.objects.values_list("category", flat=True).distinct(),
    }

    return render(request, "resources/resources.html", context)