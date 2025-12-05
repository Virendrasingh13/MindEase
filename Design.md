This document explains the **object-oriented design patterns** used in the MindEase project, why they were needed, and **where they are implemented in the codebase**.

Currently implemented patterns:

* **Factory Pattern** – in the `accounts` module
* **Strategy Pattern** (Sorting & Filtering) – in the `resources` module
* **Pipeline Pattern** (Filter Pipeline / Chain of Responsibility style) – in the `resources` module

---

## 1. Accounts Module – Factory Pattern

### 1.1 Problem Context

MindEase supports **two distinct user roles**:

* **Client**
* **Counsellor**

Both start from a common `User` model, but their profiles are very different:

* **Client**:

  * `Client` model (date of birth, primary concern, about_me, terms_accepted, etc.)
  
* **Counsellor**:

  * `Counsellor` model with:

    * Professional details (license number/type, authority, expiry, years_experience, degree, university, graduation_year)
    * Practice details (session_fee, Google Meet link, professional_experience, about_me)
    * Document uploads (license_document, degree_certificate, id_proof)
    * Many-to-many relations (specializations, therapy_approaches, languages, age_groups)
    * Certifications

Without any pattern, `accounts/views.py` would contain a lot of **duplicated and tangled logic**:

* Create `User`
* Create `Client` / `Counsellor`
* Handle file uploads
* Handle many-to-many relations
* Handle certifications
* Wrap in transactions manually
* Maintain separate “flows” for client vs counsellor

This makes the registration logic:

* Hard to read and maintain
* Hard to **extend** (e.g., adding a new role later)
* Difficult to **unit test** each creation flow

### 1.2 Solution: Factory Pattern

To separate these concerns, we implemented a **Factory Pattern** in:

* **File:** `accounts/factories.py`

This file defines:

* An **abstract factory**: `UserProfileFactory`
* Two **concrete factories**: `ClientFactory` and `CounsellorFactory`
* A small **factory selector**: `AccountFactory`

#### 1.2.1 `UserProfileFactory` (Abstract Base + Template Method)

```python
class UserProfileFactory(ABC):
    @abstractmethod
    def create_user(self, **kwargs):
        """Create and return a User instance"""
        pass

    @abstractmethod
    def create_profile(self, user, **kwargs):
        """Create and return a profile (Client or Counsellor) for the user"""
        pass

    @abstractmethod
    def setup_relationships(self, profile, **kwargs):
        """Setup many-to-many relationships for the profile"""
        pass

    @transaction.atomic
    def create_account(self, **kwargs):
        """
        Template method that orchestrates the account creation process.
        This ensures all steps are executed in the correct order within a transaction.
        """
        user = self.create_user(**kwargs)
        profile = self.create_profile(user, **kwargs)
        self.setup_relationships(profile, **kwargs)
        return user, profile
```

Key points:

* It acts as a **template** for creating any type of account.
* `create_account()`:

  * Wraps the whole process in a **single DB transaction**.
  * Guarantees that either *everything* is created or nothing is.
* Subclasses only implement:

  * `create_user(...)`
  * `create_profile(...)`
  * `setup_relationships(...)`

#### 1.2.2 `ClientFactory` – Concrete Factory for Client Accounts

**File:** `accounts/factories.py`

```python
class ClientFactory(UserProfileFactory):
    def create_user(self, **kwargs):
        user = User.objects.create_user(
            username=kwargs.get('username'),
            email=kwargs.get('email'),
            password=kwargs.get('password'),
            first_name=kwargs.get('first_name'),
            last_name=kwargs.get('last_name'),
            phone=kwargs.get('phone'),
            gender=kwargs.get('gender'),
            role='client'
        )
        user.is_active = False  # activate after email verification

        if 'profile_picture' in kwargs and kwargs['profile_picture']:
            user.profile_picture = kwargs['profile_picture']

        user.save()
        return user

    def create_profile(self, user, **kwargs):
        client = Client.objects.create(
            user=user,
            date_of_birth=kwargs.get('date_of_birth'),
            primary_concern=kwargs.get('primary_concern'),
            other_primary_concern=kwargs.get('other_primary_concern', ''),
            about_me=kwargs.get('about_me', ''),
            terms_accepted=kwargs.get('terms_accepted', False)
        )
        return client

    def setup_relationships(self, profile, **kwargs):
        # No M2M relationships for clients currently
        pass
```

**What it encapsulates:**

* All logic related to **client account creation** is inside this factory.
* The view just prepares the data and passes it to `ClientFactory`.

#### 1.2.3 `CounsellorFactory` – Concrete Factory for Counsellor Accounts

**File:** `accounts/factories.py`

```python
class CounsellorFactory(UserProfileFactory):
    def create_user(self, **kwargs):
        user = User.objects.create_user(
            username=kwargs.get('username'),
            email=kwargs.get('email'),
            password=kwargs.get('password'),
            first_name=kwargs.get('first_name'),
            last_name=kwargs.get('last_name'),
            phone=kwargs.get('phone'),
            gender=kwargs.get('gender'),
            role='counsellor'
        )
        user.is_active = False

        if 'profile_picture' in kwargs and kwargs['profile_picture']:
            user.profile_picture = kwargs['profile_picture']

        user.save()
        return user

    def create_profile(self, user, **kwargs):
        counsellor = Counsellor.objects.create(
            user=user,
            license_number=kwargs.get('license_number'),
            license_type=kwargs.get('license_type'),
            other_license_type=kwargs.get('other_license_type', ''),
            license_authority=kwargs.get('license_authority'),
            license_expiry=kwargs.get('license_expiry'),
            years_experience=kwargs.get('years_experience'),
            highest_degree=kwargs.get('highest_degree'),
            university=kwargs.get('university'),
            graduation_year=kwargs.get('graduation_year'),
            session_fee=kwargs.get('session_fee'),
            google_meet_link=kwargs.get('google_meet_link'),
            professional_experience=kwargs.get('professional_experience'),
            about_me=kwargs.get('about_me', ''),
            license_document=kwargs.get('license_document'),
            degree_certificate=kwargs.get('degree_certificate'),
            id_proof=kwargs.get('id_proof'),
            terms_accepted=kwargs.get('terms_accepted', False),
            consent_given=kwargs.get('consent_given', False),
        )
        self._create_certifications(counsellor, kwargs.get('certifications', []))
        return counsellor

    def setup_relationships(self, profile, **kwargs):
        # Attach many-to-many relationships: specializations, approaches, languages, age groups
        ...
```

It also includes helper methods like `_get_or_create_objects`, `_get_or_create_age_groups`, `_create_certifications` to keep logic reusable and clean.

#### 1.2.4 `AccountFactory` – Role-Based Factory Selector

```python
class AccountFactory:
    @staticmethod
    def get_factory(role):
        factories = {
            'client': ClientFactory(),
            'counsellor': CounsellorFactory()
        }
        factory = factories.get(role)
        if not factory:
            raise ValueError(f"Unsupported role: {role}")
        return factory

    @staticmethod
    def create_account(role, **kwargs):
        factory = AccountFactory.get_factory(role)
        return factory.create_account(**kwargs)
```

If a new role is added later (e.g., `counsellor_assistant`), we just:

* Implement `AssistantFactory(UserProfileFactory)`
* Add `'assistant': AssistantFactory()` in `get_factory()`.

### 1.3 Where It’s Used in Views

**File:** `accounts/views.py`

##### `create_client_account`

```python
def create_client_account(request):
    """Create a client account using Factory Pattern"""
    try:
        client_errors = validate_client_data(request.POST)
        if client_errors:
            return JsonResponse({'success': False, 'errors': client_errors}, status=400)

        factory = ClientFactory()
        user, client = factory.create_account(
            username=request.POST.get('email'),
            email=request.POST.get('email'),
            password=request.POST.get('password'),
            first_name=request.POST.get('first_name'),
            last_name=request.POST.get('last_name'),
            phone=request.POST.get('phone'),
            gender=request.POST.get('gender'),
            date_of_birth=request.POST.get('date_of_birth'),
            primary_concern=request.POST.get('primary_concern'),
            other_primary_concern=request.POST.get('other_primary_concern'),
            about_me=request.POST.get('about_me'),
            terms_accepted=request.POST.get('terms_accepted') == 'true',
            profile_picture=request.FILES.get('profile_picture'),
        )

        store_registration_email(request, user.email)
        send_verification_email(user)

        return JsonResponse({
            'success': True,
            'message': 'Client account created successfully. Please check your email for verification.',
            'role': 'client',
            'email': user.email
        })
    ...
```

##### `create_counsellor_account`

```python
def create_counsellor_account(request):
    """Create a counsellor account using Factory Pattern"""
    try:
        counsellor_errors = validate_counsellor_data(request.POST)
        if counsellor_errors:
            return JsonResponse({'success': False, 'errors': counsellor_errors}, status=400)

        # prepare certifications list
        certifications = []
        i = 0
        while True:
            ...
            certifications.append({...})
            i += 1

        factory = CounsellorFactory()
        user, counsellor = factory.create_account(
            username=request.POST.get('email'),
            email=request.POST.get('email'),
            password=request.POST.get('password'),
            first_name=request.POST.get('first_name'),
            last_name=request.POST.get('last_name'),
            phone=request.POST.get('phone'),
            gender=request.POST.get('gender'),
            license_number=request.POST.get('license_number'),
            license_type=request.POST.get('license_type'),
            other_license_type=request.POST.get('other_license_type'),
            license_authority=request.POST.get('license_authority'),
            license_expiry=request.POST.get('license_expiry'),
            years_experience=int(request.POST.get('years_experience')),
            highest_degree=request.POST.get('highest_degree'),
            university=request.POST.get('university'),
            graduation_year=int(request.POST.get('graduation_year')),
            session_fee=float(request.POST.get('session_fee')),
            google_meet_link=request.POST.get('google_meet_link'),
            professional_experience=request.POST.get('professional_experience'),
            about_me=request.POST.get('about_me'),
            license_document=request.FILES.get('license_document'),
            degree_certificate=request.FILES.get('degree_certificate'),
            id_proof=request.FILES.get('id_proof'),
            profile_picture=request.FILES.get('profile_picture'),
            specializations=request.POST.getlist('specializations'),
            therapy_approaches=request.POST.getlist('therapy_approaches'),
            languages=request.POST.getlist('languages'),
            age_groups=request.POST.getlist('age_groups'),
            certifications=certifications,
            terms_accepted=request.POST.get('terms_accepted') == 'true',
            consent_given=request.POST.get('consent_given') == 'true',
        )

        BackgroundVerification.objects.create(
            counsellor=counsellor,
            status='pending'
        )

        store_registration_email(request, user.email)
        send_verification_email(user)

        return JsonResponse({
            'success': True,
            'message': 'Counsellor account created successfully. Please check your email for verification...',
            'role': 'counsellor',
            'email': user.email
        })
    ...
```

### 1.4 Benefits of Factory in Accounts

* **Clean separation of responsibilities**

  * Factories handle creation logic.

* **Extensibility**

  * Adding a new role doesn’t break existing code – just add a new factory.

* **Transactional safety**

  * `create_account()` ensures user + profile + relations are created in **one atomic operation**.

---

## 2. Resources Module – Strategy + Pipeline Patterns

### 2.1 Problem Context

The **Resources** module (`resources/views.py`) needs to:

1. Apply **different filters** based on query parameters:

   * Search text
   * Type (video, article, exercise, etc.)
   * Category
   * Difficulty

2. Sort the final queryset in **multiple ways**:

   * Newest
   * Most popular
   * Alphabetical by title
   * Recommended (featured + rating + date)

If we directly put everything in the view like:

```python
if search:
    qs = qs.filter(...)
if type:
    qs = qs.filter(...)
if difficulty:
    qs = qs.filter(...)

if sort == "newest":
    qs = qs.order_by(...)
elif sort == "popular":
    qs = ...
...
```

the view becomes long, tightly coupled, and hard to extend.

### 2.2 Solution: Strategy Pattern for Sorting

**File:** `resources/strategies/sorting.py`

We define an **abstract strategy** for sorting:

```python
from abc import ABC, abstractmethod

class SortStrategy(ABC):
    @abstractmethod
    def sort(self, qs):
        pass
```

Then we implement **concrete strategies**:

```python
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
```

And finally, a **strategy registry**:

```python
SORT_STRATEGIES = {
    'newest': NewestSort(),
    'popular': PopularSort(),
    'title': TitleSort(),
    'recommended': RecommendedSort(),
}
```

**Usage in view:**

```python
# resources/views.py

from .strategies.sorting import SORT_STRATEGIES, RecommendedSort

def resource_list(request):
    qs = Resources.objects.all()
    ...
    sort_key = request.GET.get("sort", "recommended")
    sorter = SORT_STRATEGIES.get(sort_key, RecommendedSort())
    qs = sorter.sort(qs)
    ...
```

**Why this is Strategy:**

* The **algorithm for sorting** is encapsulated in strategy classes.
* At runtime, based on `sort_key`, the appropriate strategy is chosen.
* To add a new sort (e.g., `most_commented`), we just create a new `SortStrategy` subclass and add it to `SORT_STRATEGIES`.

### 2.3 Solution: Filter Pipeline (Pipeline / Chain-of-Responsibility Style)

**Files:**

* `resources/strategies/filtering.py`
* `resources/pipelines/filters_pipeline.py`

#### 2.3.1 Filter Strategy Classes

**File:** `resources/strategies/filtering.py`

```python
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
```

Each filter:

* Implements a common interface: `apply(qs, params)`.
* Either modifies the queryset or leaves it unchanged.
* Can be easily reused and tested individually.

#### 2.3.2 Filter Pipeline

**File:** `resources/pipelines/filters_pipeline.py`

```python
class FilterPipeline:
    def __init__(self, filters):
        self.filters = filters

    def run(self, qs, params):
        for f in self.filters:
            qs = f.apply(qs, params)
        return qs
```

This is a simple **Pipeline / Chain-of-Responsibility style** pattern:

* It holds a list of filter objects.
* It runs them in order, passing the queryset from one filter to the next.

#### 2.3.3 Usage in `resource_list` View

**File:** `resources/views.py`

```python
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

    ...
    return render(request, "resources/resources.html", context)
```

### 2.4 Benefits in Resources Module

* **Strategy Pattern (Sorting):**

  * Cleanly separates different sorting behaviours.
  * Easy to add new strategies without touching existing ones.
  * View stays simple: pick strategy → call `.sort(qs)`.

* **Filter Pipeline (Pipeline / Chain-of-Responsibility style):**

  * Each filter is independent and reusable.
  * Pipeline order is configurable in one place.
  * Adding/removing filters does not break the view logic.

---

## 3. Summary Table

| Module      | Pattern(s)                      | Files / Classes                                                                                                                                                                                | Responsibility                                                                                                          |
| ----------- | ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `accounts`  | **Factory Pattern**             | `accounts/factories.py` → `UserProfileFactory`, `ClientFactory`, `CounsellorFactory`, `AccountFactory`; used in `create_client_account` and `create_counsellor_account` in `accounts/views.py` | Encapsulates account creation for different roles (Client, Counsellor) inside dedicated factories with one transaction. |
| `resources` | **Strategy Pattern (Sorting)**  | `resources/strategies/sorting.py` → `SortStrategy`, `NewestSort`, `PopularSort`, `TitleSort`, `RecommendedSort`; used in `resource_list`                                                       | Chooses sorting behaviour at runtime (`?sort=newest/popular/title/recommended`) without changing view logic.            |
| `resources` | **Pipeline / Chain of Filters** | `resources/strategies/filtering.py` → `SearchFilter`, `TypeFilter`, `CategoryFilter`, `DifficultyFilter`; `resources/pipelines/filters_pipeline.py` → `FilterPipeline`                         | Applies a sequence of filters (search, type, category, difficulty) to the queryset in a clean, composable way.          |

---
