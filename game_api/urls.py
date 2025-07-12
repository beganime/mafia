from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),

    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='user_logout'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/delete/', views.profile_delete, name='profile_delete'),

    path('game/create',views.create_game, name='create_game'),
    path('game/join/', views.join_game, name='join_game'),
    path('game/search_game/',views.search_game, name='search_game'),

    path('game/<int:game_id>/', views.game_detail, name='game_detail'),
    path('game/<int:game_id>/lobby/', views.game_lobby, name='game_lobby'),
    
    path('game/<int:game_id>/start/', views.game_start, name='start_game'),
    path('game/<int:game_id>/end/', views.end_game, name='end_game'),
    path('game/<int:game_id>/next_phase/', views.next_phase, name='next_phase'),
    path('game/<int:game_id>/start_voting/', views.start_voting, name='start_voting'),
    path('game/<int:game_id>/player/<int:player_id>/kill/', views.kill_player, name='kill_player'),
    path('game/<int:game_id>/player/<int:player_id>/revive/', views.revive_player, name='revive_player'),
    path('game/<int:game_id>/player/<int:player_id>/change_role/', views.change_player_role, name='change_player_role'),
    path('game/<int:game_id>/submit_action/', views.submit_player_action, name='submit_player_action'),
    path('game/<int:game_id>/player/<int:player_id>/remove_from_lobby/', views.remove_player_from_lobby, name='remove_player_from_lobby'),
]