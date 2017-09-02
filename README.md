Django REST Offline Sync
========================

Offline Data Synchronization for Django REST Framework
------------------------------------------------------

[![Build Status](https://travis-ci.org/vsemionov/django-rest-offlinesync.svg?branch=master)](https://travis-ci.org/vsemionov/django-rest-offlinesync)


### Offline Data Synchronization

This package provides REST APIs with support for data synchronization by offline clients, such as mobile applications. This is accomplished by the following approach:
* Aggregate list endpoints per object type are exposed. This allows all objects of a given type to be retrieved in a single request, even if they are nested into different objects. For example, in the hierarchy notebook/note, there is a note list endpoint that returns all notes from all notebooks.
  - The choice to expose one endpoint per object type, as opposed to a single endpoint for all synchronized types, was made because the latter approach produces a response that is an object (as opposed to a list). This does not allow paginating responses and forces the use of a single request. Avoiding multiple round-trip times is still possible by pipelining requests for different object types.
* List endpoints allow the client to specify the minimum modification time of the returned objects. The returned data contains the request execution timestamp. To synchronize incrementally, the client must store this timestamp and send it as the minimum modification time during their next synchronization.
  - Since the synchronization is performed across multiple requests, their results may be inconsistent if objects are modified between the requests. To counter this, the endpoints also accept the maximum modification timestamp of the returned objects as a parameter. All requests after the first one in a single synchronization session should set this parameter to the request execution timestamp from the first response.
* Deletion of objects is performed softly. Upon deletion, a hidden flag is toggled, but the data itself is not removed. This allows offline clients to detect which locally-existing objects have been deleted on the server.
  - However, to preserve system resources, objects that are deleted a specified time ago are periodically removed. Also, the number of deleted objects is limited. When an object is being deleted and this limit is reached, the object with the oldest deletion timestamp is removed.
* Deleted objects are listed in separate (aggregate) endpoints, which also accept a minimum deletion timestamp parameter.
  - The server is able to detect if the generated listing is complete for the requested minimum modification timestamp. If objects may have removed due to expiry or an exceeded limit, a different response status code is returned. In this case, the client must retrieve the full list of non-deleted objects and determine the deleted ones by comparing to their local database.

#### Conflict Detection

The package also supports conflict detection when a write request is made from a client for an object, whose contents on the client are older than the contents on the server. This is beneficial for offline as well as online clients. The approach is the following:
* Endpoints that modify the state of an object accept a last modification timestamp. Clients shall set it to the object's modification timestamp in their database. If it does not match the object's modification timestamp on the server, the request is rejected.
* When a conflict occurs, it is up to the client to decide how to handle it. Some possibilities are:
  - Synchronize the newer object state on both sides.
  - Create a copy of the object.
  - Duplicate the two versions on both sides.


### Requirements

* Python 3 (tested with 3.6)
* Django (tested with 1.11)
* Django REST Framework (tested with 3.6)


### Basic Usage

1. Install the package:
```
pip install django-rest-offlinesync
```

2. Add the package to Django's list of installed apps in your project's *settings.py*:
```
INSTALLED_APPS = [
    ...
    'rest_offlinesync',
    ...
]
```

3. Inherit your models from *rest_offlinesync.models.TrackedModel*:
```
from rest_offlinesync.models import TrackedModel
class Document(TrackedModel):
    ...
```

4. Inherit your viewsets from *rest_offlinesync.sync.SyncedModelMixin*:
```
from rest_framework import viewsets
from rest_offlinesync import sync
class DocumentViewSet(sync.SyncedModelMixin,
                      ...
                      viewsets.ModelViewSet):
    ...
```

5. Declare your viewsets' querysets:
```
    queryset = Document.objects.all()
```
NOTE: This is required because the set of viewset mixins in this package override *get_queryset()* to chain-manipulate the queryset of each mixin, and the "base" queryset is defined with this attribute. If you override *get_queryset()* to perform per-request queryset manipulation, you **must** call the superclass's method and start from its result.

6. Configure the expiry delay of deleted objects in *settings.py* (optional):
```
REST_OFFLINESYNC = {
    'DELETED_EXPIRY_DAYS': 30,
    ...
}
```
You can use `None` or `0` for no expiry. The default is no expiry.

Your viewsets will now:
* accept minimum and maximum modification timestamp arguments (*since* and *until*) for their list endpoints
  - these endpoints return both timestamps in the response body
  - if the maximum modification timestamp is not specified, the execution time is returned
* accept a current modification timestamp argument (*at*) for their write endpoints, and concurrency-safely enforce it
  - if the specified modification timestamp does not match the current one, the operation is not performed and http status 409 is returned
  - write operations are guaranteed to increment the object modification timestamp for reliable conflict detection
* perform soft deletion
* not show deleted objects in list results
* return http status 404 for requests to deleted objects
* expose endpoints that list deleted objects (*./deleted/*)
  - these endpoints indicate possibly incomplete results by returning http status 206

#### Clearing Expired Deleted Objects

A management command is provided to clear expired deleted objects. To invoke it:
```
python manage.py cleardeleted
```
The output is the number of cleared objects per tracked model.


### Model Relationships, Resource Nesting and Aggregation

Relationships between synchronized models are supported by the *NestedModelMixin* viewset mixin. It ensures the following:
* read requests fail with http status 404 if the parent object does not exist or is deleted
* write requests fail with http status 404 if the parent object does not exist
  - write requests to objects with deleted parents are allowed in order to ease the synchronization of updated data

The mixin also supports nested viewsets, i.e. ones whose subsequent URL path components correspond to subsequent levels in the model relationship hierarchy. During the creation of new objects, the mixin handles the population of the parent ID field from the value in the request path. It is guaranteed that if removal of an expired deleted parent object is performed during creation of a child of the same object, the creation will either fail with status 404, or succeed before the actual removal (race conditions, leading to database constraint violation errors, and therefore to internal server errors, are prevented).

It is also possible to define aggregate viewsets, i.e. ones that operate over more than one relationship level (e.g. on all grandchildren of an object, regardless of its direct children).

To enable this mixin:
1. Inherit your viewsets from it:
```
from rest_offlinesync import nest
class DocumentViewSet(nest.NestedSyncedModelMixin,
                      ...
                      viewsets.ModelViewSet):
```
Note that this mixin does not inherit from *NestedModelMixin*, so it is necessary to explicitly inherit from the latter one.

2. Configure the mixin by setting the following attributes to the viewset:
```
    parent_model = User                                 # the viewset's parent in the model hierarchy
    parent_path_model = User                            # the viewset's parent in the URL path hierarchy
    safe_parent_path = False                            # whether the mixin should skip checking the parent URL component; False if it is already confirmed, e.g. by permissions
    object_filters = {'user_id': 'user_username'}       # filters to apply to the queryset; keys are queryset filter argument names, values are URL argument names
    parent_filters = {'username': 'user_username'}      # filters to apply to the parent queryset
    parent_path_filters = {'username': 'user_username'} # filters to apply to the parent path queryset, if the viewset is aggregate (i.e. if parent_model != parent_path_model)
```

The *NestedModelMixin* mixin is also usable standalone (not combined with the *SyncedModelMixin*) and can be applied to any model (not inheriting *TrackedModel*).


### Resource Quotas

Quotas (limits) of synchronized models are supported by the *LimitedNestedSynced* viewset mixin. The limits are two types - ones for active objects and ones for deleted objects. They are given and applied on a per-parent basis. Also, different types of parent models may have different limits on their child models. The *LimitedNestedSynced* mixin performs the following tasks:
* concurrency-safely enforces limits during creation and moving of active objects; if a limit is exceeded, the requested operation is not performed, and an http status 402 is returned
* evicts the oldest deleted peer(s) of a deleted object if the limits of deleted objects are exceeded
* detects if the deleted list endpoint may have returned incomplete results, due to the above eviction, and, if necessary to indicate this condition, modifies the returned http status to 206

NOTE: It is assumed that modification of an object's parent (i.e. moving) will be performed **only** through an aggregate viewset.

To enable this mixin:
1. Configure limits in *settings.py*:
```
REST_OFFLINESYNC = {
    ...
    'OBJECT_LIMITS': {
        'auth.User': {               # one key for every parent model with child limits
            'api.Document': (2, 2),  # one key for every limited child model
                                     # values are a pair of active and deleted object limits
                                     # use 0 or None for unlimited; default is unlimited
        },
    },
}
```

2. Inherit your viewsets from it:
```
from rest_offlinesync import limit
class DocumentViewSet(limit.LimitedNestedSyncedModelMixin,
                      ...
                      viewsets.ModelViewSet):
```
Note that this mixin inherits from the other ones, so it is not necessary to explicitly inherit from the other ones.

3. Configure the mixin by setting the following attribute to the viewset:
```
    parent_key_filter = 'user_id'  # the name of the database column, which references the parent model
```

### Example Project

For a working example project that integrates this package, see the */example* directory. To run it:
```
cd example
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

#### Current Limitations

* There is no way to retrieve an object, whose parent is deleted. This can be a problem especially if an object is moved to a deleted parent. Then, a syncing client has no way to notice the move. The object would eventually be removed from the server, but will be kept indefinitely on the client.
* The *NestedModelMixin* currently ensures http 404 errors for deleted parents only if they are direct parents.
