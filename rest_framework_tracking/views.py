from django.conf import settings
from django.contrib.admindocs.views import simplify_regex
from django.contrib.sites.models import Site
from django.core.urlresolvers import RegexURLResolver, RegexURLPattern
from django.core.validators import EMPTY_VALUES
from django.utils.module_loading import import_string

from rest_framework.response import Response
from rest_framework.views import APIView

from .mixins import LoggingMixin
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

    def _is_drf_trakcing__view(self, pattern):
        return hasattr(pattern.callback, 'cls') and issubclass(pattern.callback.cls, APIView)\
               and issubclass(pattern.callback.cls, LoggingMixin)

    def _is_format_endpoint(self, pattern):
        return '?P<format>' in pattern._regex

    def get_pattern_path(self, pattern, parent_pattern=None):
        if parent_pattern:
            name_parent = simplify_regex(parent_pattern.regex.pattern).strip('/')
            return "/{0}{1}".format(name_parent, simplify_regex(pattern.regex.pattern))
        return simplify_regex(pattern.regex.pattern)

    def get_pattern_regex_pattern(self, pattern, parent_pattern=None):
        if parent_pattern:
            return r"{0}{1}".format(parent_pattern.regex.pattern,
                                    pattern.regex.pattern)
        return pattern.regex.pattern

    def get_all_regex_patterns(self, urlpatterns, parent_pattern=None):
        for pattern in urlpatterns:
            if isinstance(pattern, RegexURLResolver):
                parent_pattern = None if pattern._regex == "^" else pattern
                self.get_all_regex_patterns(urlpatterns=pattern.url_patterns, parent_pattern=parent_pattern)
            elif isinstance(pattern, RegexURLPattern) and self._is_drf_trakcing__view(pattern) \
                 and not self._is_format_endpoint(pattern):
                url = {'path': self.get_pattern_path(pattern, parent_pattern),
                       'regex': self.get_pattern_regex_pattern(pattern, parent_pattern)}
                self.url_patterns.append(url)

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
            counts[regex['path']] = qs.filter(path__regex=simplify_regex(regex['regex'])).count()
        return counts

    def get(self, request, *args, **kwargs):
        patterns = self.get_urlconf_patterns()
        print patterns
        qs = self.get_queryset()

        today = date.today()
        current_window = self.get_window(today, 0)
        previous_window = self.get_window(today, -1)
        current_qs = qs.filter(requested_at__range=current_window)
        previous_qs = qs.filter(requested_at__range=previous_window)

        current = {'usage': self.get_path_counts(patterns, current_qs),
                   'window': current_window}
        previous = {'usage': self.get_path_counts(patterns, previous_qs),
                    'window': previous_window}

        data = {
                'current': current,
                'previous': previous,
                }
        return Response(APIRequestLogSerializer(data).data)
