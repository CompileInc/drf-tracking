from rest_framework import serializers

class APIRequestLogSerializer(serializers.Serializer):
    current = serializers.IntegerField()
    previous = serializers.IntegerField()
