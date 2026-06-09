from django.contrib import admin

from .models import Chats, ChatMembers, Friends, FriendRequests

admin.site.register(Chats)
admin.site.register(ChatMembers)
admin.site.register(Friends)
admin.site.register(FriendRequests)