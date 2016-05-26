from django.conf import settings
from django.contrib.admindocs.views import simplify_regex
from django.contrib.sites.models import Site
from django.core.urlresolvers import RegexURLResolver, RegexURLPattern
from django.core.validators import EMPTY_VALUES
from django.utils.module_loading import import_string

from rest_framework.response import Response
from rest_framework.views import APIView

from .models import APIRequestLog
from .serializers import APIRequestLogSerializer

from datetime import date
from datetime import timedelta
from importlib import import_module
import re


FILTER_CURRENT_HOST = getattr(settings, 'DRF_TRACKING_USAGE_CURRENT_SITE', True)
FILTER_USAGE_METHOD = getattr(settings, 'DRF_TRACKING_USAGE_METHOD', [])

class APIRequestList(APIView):
    '''
    API usage current and previous billing cycle.

    Returns:
        The total number of countable requests made to Compile API for each path
    '''
    model = APIRequestLog
    serializer_class = APIRequestLogSerializer

    def get_queryset(self):
        qs = self.model._default_manager.all()

        qs = qs.filter(user=self.request.user)

        if FILTER_CURRENT_HOST:
            site = Site.objects.get_current().domain
            qs = qs.filter(host=site)

        if FILTER_USAGE_METHOD not in EMPTY_VALUES:
            qs = qs.filter(method__in=FILTER_USAGE_METHOD)

        return qs

    def get_window(self, today, index):
        '''
        Returns date window range
            index: 0 = current
            index: -1 = previous
        '''
        start = date(today.year, today.month+index, 1)
        end = date(today.year, start.month+1, 1) - timedelta(days=1)
        return [start, end]

    def get_urlconf(self):
        urlconf = settings.ROOT_URLCONF
        if hasattr(self.request, 'urlconf'):
            urlconf = self.request.urlconf

        try:
            root_urlconf = import_string(urlconf)
        except ImportError:
            root_urlconf = import_module(urlconf)

        return root_urlconf

    def _is_drf_view(self, pattern):
        return hasattr(pattern.callback, 'cls') and issubclass(pattern.callback.cls, APIView)

    def _is_format_endpoint(self, pattern):
        return '?P<format>' in pattern._regex

    def get_all_regex_patterns(self, urlpatterns, parent_pattern=None):
        for pattern in urlpatterns:
            if isinstance(pattern, RegexURLResolver):
                parent_pattern = None if pattern._regex == "^" else pattern
                self.get_all_regex_patterns(urlpatterns=pattern.url_patterns, parent_pattern=parent_pattern)
            elif isinstance(pattern, RegexURLPattern) and self._is_drf_view(pattern) and not self._is_format_endpoint(pattern):
                self.url_patterns.append(pattern.regex)

    def get_urlconf_patterns(self):
        root_urlconf = self.get_urlconf()
        self.url_patterns = []

        if hasattr(root_urlconf, 'urls'):
            self.get_all_regex_patterns(root_urlconf.urls.urlpatterns)
        else:
            self.get_all_regex_patterns(root_urlconf.urlpatterns)

        return self.url_patterns

    def get_path_counts(self, patterns, qs):
        counts = {}
        for regex in patterns:
            counts[regex.pattern] = qs.filter(path__regex=simplify_regex(regex.pattern)).count()
        return counts

    def get(self, request, *args, **kwargs):
        patterns = self.get_urlconf_patterns()
        qs = self.get_queryset()

        today = date.today()
        current_qs = qs.filter(requested_at__range=self.get_window(today, 0))
        previous_qs = qs.filter(requested_at__range=self.get_window(today, -1))

        current = self.get_path_counts(patterns, current_qs)
        previous = self.get_path_counts(patterns, previous_qs)

        data = {
                'current': current,
                'previous': previous,
                }
        return Response(APIRequestLogSerializer(data).data)
