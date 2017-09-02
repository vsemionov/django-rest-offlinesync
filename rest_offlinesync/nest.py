from django.db import transaction
from django.shortcuts import get_object_or_404

from .models import TrackedModel
from .mixin import ViewSetMixin


class NestedModelMixin(ViewSetMixin):

    parent_model = None
    parent_path_model = None
    safe_parent_path = False

    object_filters = {}
    parent_filters = {}
    parent_path_filters = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.deleted_parent = False

    def get_parent_name(self):
        return self.parent_model._meta.model_name

    def is_aggregate(self):
        return self.parent_path_model is not self.parent_model

    def _filter_queryset(self, queryset, filters, is_parent):
        filter_kwargs = {expr: self.kwargs[kwarg] for expr, kwarg in filters.items()}

        if self.deleted_parent is not None:
            model = queryset.model if is_parent else self.parent_model
            if issubclass(model, TrackedModel):
                expr = 'deleted' if is_parent else self.get_parent_name() + '__deleted'
                filter_kwargs.update({expr: self.deleted_parent})

        queryset = queryset.filter(**filter_kwargs)

        return queryset

    def get_parent_queryset(self, path, lock):
        if path:
            model = self.parent_path_model
            filters = self.parent_path_filters if self.is_aggregate() else self.parent_filters
        else:
            model = self.parent_model
            filters = self.parent_filters

        queryset = model.objects

        queryset = self._filter_queryset(queryset, filters, True)

        if lock:
            queryset = queryset.select_for_update()

        return queryset

    def get_parent(self, path, lock):
        queryset = self.get_parent_queryset(path, lock)

        parent = get_object_or_404(queryset)

        return parent

    def get_queryset(self):
        queryset = super().get_queryset()

        queryset = self._filter_queryset(queryset, self.object_filters, False)

        return queryset

    def list(self, request, *args, **kwargs):
        if not self.safe_parent_path:
            self.get_parent(True, False)

        return super().list(request, *args, **kwargs)

    def locked_parent(self, parent):
        queryset = self.parent_model.objects.filter(pk=parent.pk)

        queryset = queryset.select_for_update()

        locked = get_object_or_404(queryset)

        return locked

    def create(self, request, *args, **kwargs):
        self.deleted_parent = None
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self.deleted_parent = None
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self.deleted_parent = None
        return super().destroy(request, *args, **kwargs)

    @transaction.atomic(savepoint=False)
    def perform_create(self, serializer):
        parent_name = self.get_parent_name()

        save_kwargs = {}

        if self.is_aggregate():
            self.locked_parent(serializer.validated_data[parent_name])

        else:
            parent = self.get_parent(False, True)

            save_kwargs = {parent_name: parent}

        serializer.save(**save_kwargs)
