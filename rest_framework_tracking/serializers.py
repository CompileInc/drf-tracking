from rest_framework import serializers

class APIRequestLogSerializer(serializers.Serializer):
    current = serializers.DictField()
    previous = serializers.DictField()
