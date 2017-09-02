from django.conf import settings
from django.db import transaction
from django.db.models import Subquery
from django.db.models import Count, Min
from django.shortcuts import get_object_or_404
from rest_framework import exceptions, status, decorators

from .models import TrackedModel
from .nest import NestedModelMixin
from .sync import SyncedModelMixin


class LimitExceededError(exceptions.APIException):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = 'limit exceeded'


class LimitedNestedSyncedModelMixin(NestedModelMixin, SyncedModelMixin):
    parent_key_filter = None

    def get_limit(self, deleted):
        limits = getattr(settings, 'REST_OFFLINESYNC', None) and settings.REST_OFFLINESYNC.get('OBJECT_LIMITS')
        if not limits:
            return None

        parent_limits = limits.get(self.parent_model._meta.label)
        if not parent_limits:
            return None

        child_limit = parent_limits.get(self.queryset.model._meta.label)
        if not child_limit:
            return None

        limit = child_limit[int(deleted)]
        if not limit:
            return None

        return limit

    def _is_potentially_evicted(self):
        del_limit = self.get_limit(True)
        if not del_limit:
            return False

        filter_kwargs = {expr: self.kwargs[kwarg] for expr, kwarg in self.object_filters.items()}
        filter_kwargs['deleted'] = True

        results = self.queryset.filter(**filter_kwargs)
        results = results.values(self.parent_key_filter)
        results = results.annotate(ndel=Count('*'), oldest=Min('updated'))
        results = results.filter(ndel__gte=del_limit)

        if self.since is not None:
            results = results.filter(oldest__gte=self.since)

        return len(results) > 0

    @decorators.list_route(suffix='Archive')
    def deleted(self, request, *args, **kwargs):
        response = super().deleted(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            if self._is_potentially_evicted():
                response.status_code = status.HTTP_206_PARTIAL_CONTENT

        return response

    def _check_active_limits(self, parent):
        limit = self.get_limit(False)
        if not limit:
            return

        object_type = self.queryset.model

        child_set_name = object_type._meta.model_name + '_set'
        child_set = getattr(parent, child_set_name)

        if issubclass(object_type, TrackedModel):
            child_set = child_set.filter(deleted=False)

        if child_set.count() >= limit:
            raise LimitExceededError('exceeded limit of %d %s per %s' %
                                     (limit, object_type._meta.verbose_name_plural, parent._meta.verbose_name))

    def _evict_deleted_peers(self, instance):
        limit = self.get_limit(True)
        if not limit:
            return

        filter_kwargs = {}
        filter_kwargs[self.parent_key_filter] = getattr(instance, self.parent_key_filter)
        filter_kwargs['deleted'] = True

        delete_ids = Subquery(self.queryset.filter(**filter_kwargs).order_by('-updated', '-id')[limit:].values('id'))

        delete_objs = self.queryset.filter(id__in=delete_ids)
        delete_objs.delete()

    @transaction.atomic(savepoint=False)
    def perform_create(self, serializer):
        parent_name = self.get_parent_name()

        save_kwargs = {}

        if self.is_aggregate():
            parent = self.locked_parent(serializer.validated_data[parent_name])

        else:
            parent = self.get_parent(False, True)

            save_kwargs = {parent_name: parent}

        self._check_active_limits(parent)

        serializer.save(**save_kwargs)

    @transaction.atomic(savepoint=False)
    def perform_update(self, serializer):
        if self.is_aggregate():
            parent = self.locked_parent(serializer.validated_data[self.get_parent_name()])

            self._check_active_limits(parent)

        return super().perform_update(serializer)

    def perform_destroy(self, instance):
        super().perform_destroy(instance)

        self._evict_deleted_peers(instance)
