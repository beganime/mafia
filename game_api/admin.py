from django.contrib import admin
from .models import Game, Player, Round, PlayerAction

admin.site.register(Game)
admin.site.register(Player)
admin.site.register(Round)
admin.site.register(PlayerAction)