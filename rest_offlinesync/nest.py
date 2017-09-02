from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import exceptions

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
        queryset = self.parent_model.objects.select_for_update()

        try:
            locked = queryset.get(pk=parent.pk)

        except self.parent_model.DoesNotExist:
            raise exceptions.APIException({self.get_parent_name(): "object no longer exists"})

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
            # TODO: This lock should ideally be optimized away to save a database query.
            # To accomplish this:
            #  - the parent should be locked when its queryset is evaluated and validated
            #  - the transaction block should be moved to create()
            #  - this branch should be removed
            #  - the documentation should warn that locking of the parent is a responsibility of the library's client
            # However, the parent queryset is evaluated also during list requests, which handled without a transaction.
            # This causes internal server errors when trying to lock the queryset with select_for_update().
            # Another problem is that the parent set may have been created at initialization time,
            # outside of a transaction.
            self.locked_parent(serializer.validated_data[parent_name])

        else:
            parent = self.get_parent(False, True)

            save_kwargs = {parent_name: parent}

        serializer.save(**save_kwargs)
