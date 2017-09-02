from rest_framework import decorators

from .mixin import ViewSetMixin


class DeletableModelMixin(ViewSetMixin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.deleted_object = False

    def get_queryset(self):
        queryset = super().get_queryset()

        if self.deleted_object is not None:
            queryset = queryset.filter(deleted=self.deleted_object)

        return queryset

    @decorators.list_route(suffix='Archive')
    def deleted(self, request, *args, **kwargs):
        self.deleted_object = True
        return self.list(request, *args, **kwargs)

    def perform_destroy(self, instance):
        instance.deleted = True
        instance.save()
