from django.conf import settings
from django.contrib.sites.models import Site
from django.core.validators import EMPTY_VALUES

from rest_framework.views import APIView
from rest_framework.response import Response

from .models import APIRequestLog

from datetime import date
from datetime import timedelta


FILTER_CURRENT_HOST = getattr(settings, 'DRF_TRACKING_USAGE_CURRENT_SITE', True)
FILTER_USAGE_METHOD = getattr(settings, 'DRF_TRACKING_USAGE_METHOD', [])

class APIRequestList(APIView):
    '''
    API usage current and previous billing cycle.

    Returns:
        The total number of countable requests made to Compile API for each path
    '''
    model = APIRequestLog

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


    def get(self, request, *args, **kwargs):
        qs = self.get_queryset()
        today = date.today()
        return Response({
                'current': qs.filter(requested_at__range=self.get_window(today, 0)).count(),
                'previous': qs.filter(requested_at__range=self.get_window(today, -1)).count()
            })
