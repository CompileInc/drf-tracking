from django.conf.urls import url
from .views import APIRequestList

urlpatterns = [
                url(r'^$', APIRequestList.as_view(), name='drftracking-usage'),
              ]
