from django.contrib import admin

from .models import Chats, ChatMembers, Friends, FriendRequests, Messages, Attachments

admin.site.register(Chats)
admin.site.register(ChatMembers)
admin.site.register(Friends)
admin.site.register(FriendRequests)
admin.site.register(Messages)
admin.site.register(Attachments)
