import random
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, UserChangeForm
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone 

from .models import Game, Player, Round, PlayerAction, User
from .forms import GameSettingsForm, PlayerActionForm, UserUpdateForm ,AddPlayerForm, ChangePlayerRoleForm, JoinGameForm 


def home(request):
    return render(request,'game_api/home.html')

@login_required
def create_game(request):
    if request.method == 'POST':
        form = GameSettingsForm(request.POST)
        if form.is_valid():
            game = form.save(commit=False)
            game.host = request.user
            game.save()
            Player.objects.create(
                game=game,
                user=request.user,
                nickname=request.user.username,
                role='CIVILIAN', # Роль будет изменена при старте игры
                is_host=True,
                order_in_game=1
            )
            messages.success(request, f"Игра #{game.id} создана! Вы являетесь ведущим.")
            return redirect('game_lobby', game_id=game.id)
    else:
        form = GameSettingsForm()
        return render(request,'game_api/create_game.html',{"form":form})

def join_game(request):
    if request.method == 'POST':
        form  = JoinGameForm(request.POST)
        if form.is_valid():
            game_id = form.cleaned_data['game_id']
            nickname = form.cleaned_data['nickname']
            try:
                game = Game.objects.get(id=game_id)
            except Game.DoesNotExist:
                messages.error(request, "Игра с таким ID не найдена.")
                return render(request, 'game_api/join_game.html', {'form': form})

            if game.status != 'LOBBY':
                messages.error(request, "Игра уже началась или завершена. Подключение возможно только в статусе Лобби.")
                return render(request, 'game_api/join_game.html', {'form': form})

            if Player.objects.filter(game=game, nickname=nickname).exists():
                messages.error(request, f"Никнейм '{nickname}' уже занят в этой игре. Выберите другой.")
                return render(request, 'game_api/join_game.html', {'form': form})

            if request.user.is_authenticated and Player.objects.filter(game=game, user=request.user).exists():
                messages.warning(request, "Вы уже присоединились к этой игре. Перенаправляем вас в лобби.")
                return redirect('game_lobby', game_id=game.id)
            
            if request.user.is_authenticated and request.user == game.host and Player.objects.filter(game=game, user=request.user, is_host=True).exists():
                messages.warning(request, "Вы являетесь ведущим этой игры и уже добавлены как игрок. Перенаправляем вас в лобби.")
                return redirect('game_lobby', game_id=game.id)

            player = Player.objects.create(
                game=game,
                user=request.user if request.user.is_authenticated else None,
                nickname=nickname,
                role='CIVILIAN', # Роль будет изменена при старте игры
                is_host=False,
                order_in_game=game.players.count() + 1
            )
            messages.success(request, f"Вы присоединились к игре #{game.id} как {nickname}!")
            if not request.user.is_authenticated:
                request.session['player_id'] = player.id
                request.session['game_id'] = game.id
            return redirect('game_detail', game_id=game.id) 

    else:
        form = JoinGameForm()
        return render(request,'game_api/join_game.html',{"form":form})

def game_detail(request,game_id):
    game = get_object_or_404(Game, id=game_id)
    players = Player.objects.filter(game=game).select_related('user').order_by('order_in_game')
    current_round = game.rounds.order_by('-round_number').first()
    player_action = PlayerAction.objects.order_by('-timestamp')

    is_player_in_game = False
    current_player_profile = None

    if request.user.is_authenticated:
        current_player_profile = Player.objects.filter(game=game, user=request.user).first()
        if current_player_profile:
            is_player_in_game = True
    elif 'player_id' in request.session and request.session['game_id'] == game_id:
        try:
            current_player_profile = Player.objects.get(id=request.session['player_id'], game=game)
            is_player_in_game = True
        except Player.DoesNotExist:
            pass 

    player_action_form = None
    if is_player_in_game and game.status in ['DAY', 'NIGHT', 'VOTING'] and current_player_profile.is_alive:
        player_action_form = PlayerActionForm(game_id=game_id, current_player=current_player_profile, current_phase=current_round.phase)
        
    context = {
        'game': game,
        'players': players,
        'current_round': current_round,
        'is_player_in_game': is_player_in_game,
        'current_player_profile': current_player_profile, 
        'player_action_form': player_action_form, 
        'player_action':player_action,
    }
    return render(request, 'game_api/game_detail.html', context)

def game_lobby(request,game_id):
    game = get_object_or_404(Game, id=game_id) 
    if game.host != request.user: 
        messages.error(request, "Только ведущий может управлять лобби этой игры.")
        return redirect('game_detail', game_id=game.id) 
        
    if game.status != 'LOBBY':
        messages.warning(request, "Эта игра уже не в лобби.")
        return redirect('game_detail', game_id=game.id)
    
    if request.method == 'POST':
        form = AddPlayerForm(request.POST)
        if form.is_valid():
            nickname = form.cleaned_data['nickname']
            if Player.objects.filter(game=game, nickname=nickname).exists():
                messages.error(request, f"Игрок с никнеймом '{nickname}' уже существует в этой игре.")
            else:
                Player.objects.create(game=game, nickname=nickname, role='CIVILIAN', is_alive=True) # Роль пока временная
                messages.success(request, f"Игрок '{nickname}' добавлен.")
            return redirect('game_lobby', game_id=game.id)
    else:
        form = AddPlayerForm()

    players = game.players.all().order_by('id') 
    return render(request, 'game_api/game_lobby.html', {'game': game, 'players': players, 'form': form})


def is_host_of_game(view_func):
    def _wrapped_view(request, game_id, *args, **kwargs):
        game = get_object_or_404(Game, id=game_id)
        if request.user.is_authenticated and game.host == request.user:
            return view_func(request, game_id, *args, **kwargs)
        messages.error(request, "У вас нет прав для выполнения этого действия.")
        return redirect('game_detail', game_id=game.id) 
    return _wrapped_view

@transaction.atomic
def process_night_actions_logic(game, current_round_obj):
    """
    Обрабатывает действия, произошедшие ночью.
    Возвращает словарь с результатами и событиями.
    """
    events = []
    killed_player = None
    
    mafia_actions = PlayerAction.objects.filter(
        round=current_round_obj,
        action_type='MAFIA_KILL'
    )
    mafia_targets = {}
    for action in mafia_actions:
        if action.target:
            mafia_targets[action.target.id] = mafia_targets.get(action.target.id, 0) + 1
    
    mafia_target_id = None
    if mafia_targets:
        mafia_target_id = max(mafia_targets, key=mafia_targets.get)
        max_votes = mafia_targets[mafia_target_id]
        if list(mafia_targets.values()).count(max_votes) > 1:
            events.append("Мафия не смогла договориться или была ничья в голосовании. Никто не убит этой ночью.")
            mafia_target_id = None 
        elif mafia_target_id:
            events.append(f"Мафия выбрала игрока {get_object_or_404(Player, id=mafia_target_id).nickname} для убийства.")
            current_round_obj.mafia_kill_target = get_object_or_404(Player, id=mafia_target_id)
            current_round_obj.save()

    doctor_actions = PlayerAction.objects.filter(
        round=current_round_obj,
        action_type='DOCTOR_HEAL'
    )
    doctor_heals = {}
    for action in doctor_actions:
        if action.target:
            doctor_heals[action.target.id] = doctor_heals.get(action.target.id, 0) + 1
    
    doctor_target_id = None
    if doctor_heals:
        doctor_target_id = max(doctor_heals, key=doctor_heals.get)
        events.append(f"Доктор выбрал игрока {get_object_or_404(Player, id=doctor_target_id).nickname} для лечения.")
        current_round_obj.doctor_heal_target = get_object_or_404(Player, id=doctor_target_id)
        current_round_obj.save()

    commissioner_actions = PlayerAction.objects.filter(
        round=current_round_obj,
        action_type='COMMISSIONER_CHECK'
    )
    commissioner_checks = {}
    for action in commissioner_actions:
        if action.target:
            commissioner_checks[action.target.id] = commissioner_checks.get(action.target.id, 0) + 1

    commissioner_target_id = None
    if commissioner_checks:
        commissioner_target_id = max(commissioner_checks, key=commissioner_checks.get)
        target_player = get_object_or_404(Player, id=commissioner_target_id)
        events.append(f"Комиссар проверил игрока {target_player.nickname}. Его роль: {target_player.get_role_display()}.") # get_role_display() для читабельности
        current_round_obj.commissioner_check_target = target_player
        current_round_obj.save()

    if mafia_target_id:
        if doctor_target_id == mafia_target_id:
            events.append(f"Игрок {get_object_or_404(Player, id=mafia_target_id).nickname} был спасен доктором!")
        else:
            killed_player = get_object_or_404(Player, id=mafia_target_id)
            if killed_player.is_alive:
                killed_player.is_alive = False
                killed_player.save()
                events.append(f"Ночью был убит игрок {killed_player.nickname} (Роль: {killed_player.get_role_display()}).")
            else:
                events.append(f"Игрок {killed_player.nickname} уже был мертв.")
    else:
        events.append("Ночью никто не был убит.")

    current_round_obj.events += "\n" + "\n".join(events) if events else ""
    current_round_obj.save()

    return {
        "message": "Ночные действия обработаны.",
        "events": events,
        "killed_player": killed_player.id if killed_player else None
    }


@transaction.atomic
def process_vote_logic(game, current_round_obj):
    """
    Обрабатывает результаты голосования.
    Возвращает словарь с результатами и событиями.
    """
    events = []
    executed_player = None

    votes = PlayerAction.objects.filter(
        round=current_round_obj,
        action_type='VOTE'
    )
    vote_counts = {}
    for action in votes:
        if action.target:
            vote_counts[action.target.id] = vote_counts.get(action.target.id, 0) + 1
    
    if not vote_counts:
        events.append("Никто не проголосовал. Никто не казнен.")
    else:
        max_votes = 0
        most_voted_players = []
        for player_id, count in vote_counts.items():
            if count > max_votes:
                max_votes = count
                most_voted_players = [player_id]
            elif count == max_votes:
                most_voted_players.append(player_id)
        
        if len(most_voted_players) > 1:
            events.append("Ничья в голосовании. Никто не казнен.")
        else:
            executed_player_id = most_voted_players[0]
            executed_player = get_object_or_404(Player, id=executed_player_id)
            if executed_player.is_alive:
                executed_player.is_alive = False
                executed_player.save()
                current_round_obj.executed_player = executed_player
                events.append(f"По результатам голосования был казнен игрок {executed_player.nickname} (Роль: {executed_player.get_role_display()}).")
            else:
                events.append(f"Игрок {executed_player.nickname} уже был мертв и не мог быть казнен.")

    current_round_obj.events += "\n" + "\n".join(events) if events else ""
    current_round_obj.save()

    return {
        "message": "Голосование обработано.",
        "events": events,
        "executed_player_id": executed_player.id if executed_player else None
    }

@login_required
@is_host_of_game
@transaction.atomic
def game_start(request, game_id):
    game = get_object_or_404(Game, id=game_id)

    if game.status != 'LOBBY':
        messages.error(request, "Игру можно начать только из статуса 'Лобби'.")
        return redirect('game_detail', game_id=game.id)

    players = list(game.players.all())
    game.players_count = len(players)
    game.save()

    if len(players) < 2: 
        messages.error(request, f"Недостаточно игроков для старта. Необходимо минимум 2 игрока, сейчас {len(players)}.")
        return redirect('game_lobby', game_id=game.id)

    roles_pool = []
    roles_pool.extend(['MAFIA'] * game.mafia_count)
    roles_pool.extend(['DOCTOR'] * game.doctor_count)
    roles_pool.extend(['COMMISSIONER'] * game.commissioner_count)
    
    civilian_count = len(players) - len(roles_pool)
    if civilian_count < 0:
        messages.error(request, "Количество ролей превышает количество игроков. Проверьте настройки игры.")
        return redirect('game_lobby', game_id=game.id)

    roles_pool.extend(['CIVILIAN'] * civilian_count)

    random.shuffle(roles_pool) 

    for i, player in enumerate(players):
        player.role = roles_pool.pop()
        player.is_alive = True
        player.order_in_game = i + 1 
        player.save()
    
    game.status = 'DAY' 
    game.current_round = 1
    game.start_time = timezone.now()
    game.save()

    Round.objects.create(
        game=game,
        round_number=game.current_round,
        phase='DAY',
        events="Игра началась. Роли распределены. Начинается День 1."
    )

    messages.success(request, "Игра успешно начата! Роли распределены.")
    return redirect('game_detail', game_id=game.id)


@login_required
@is_host_of_game
def end_game(request, game_id):
    game = get_object_or_404(Game, id=game_id)

    if game.status == 'FINISHED':
        messages.warning(request, "Игра уже завершена.")
        return redirect('game_detail', game_id=game.id)

    game.status = 'FINISHED'
    game.end_time = timezone.now()
    game.save()
    
    messages.info(request, "Игра была завершена вручную ведущим.")
    return redirect('game_detail', game_id=game.id)

@login_required
@is_host_of_game
@transaction.atomic
def next_phase(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    current_round_obj = get_object_or_404(Round, game=game, round_number=game.current_round)

    next_phase_in_round_map = {
        'DAY': 'NIGHT',
        'NIGHT': 'VOTING',
    }

    if game.status == 'FINISHED':
        messages.info(request, "Игра уже завершена.")
        return redirect('game_detail', game_id=game.id)

    if game.status not in ['DAY', 'NIGHT', 'VOTING']:
        messages.error(request, "Невозможно перейти к следующей фазе, игра не находится в активном состоянии.")
        return redirect('game_detail', game_id=game.id)

    current_phase = current_round_obj.phase
    events_log = []

    if current_phase == 'NIGHT':
        night_results = process_night_actions_logic(game, current_round_obj)
        events_log.extend(night_results.get('events', []))
        messages.info(request, night_results.get('message', ''))

        mafia_alive = game.players.filter(role='MAFIA', is_alive=True).count()
        civilians_alive = game.players.filter(role__in=['CIVILIAN', 'DOCTOR', 'COMMISSIONER'], is_alive=True).count()
        
        if mafia_alive >= civilians_alive:
            game.status = 'FINISHED'
            game.end_time = timezone.now()
            game.save()
            messages.success(request, "Ночь завершена. Мафия победила!")
            return redirect('game_detail', game_id=game.id)
        elif mafia_alive == 0:
            game.status = 'FINISHED'
            game.end_time = timezone.now()
            game.save()
            messages.success(request, "Ночь завершена. Мирные жители победили!")
            return redirect('game_detail', game_id=game.id)

        new_phase_for_current_round = next_phase_in_round_map.get(current_phase) 
        current_round_obj.phase = new_phase_for_current_round
        game.status = new_phase_for_current_round
        messages.success(request, f"Игра перешла в фазу '{new_phase_for_current_round}' Раунда {game.current_round}.")
        current_round_obj.events += "\n" + "\n".join(events_log) if events_log else ""
        current_round_obj.save()
        game.save()
        return redirect('game_detail', game_id=game.id)

    elif current_phase == 'VOTING':
        vote_results = process_vote_logic(game, current_round_obj)
        events_log.extend(vote_results.get('events', []))
        messages.info(request, vote_results.get('message', ''))

        mafia_alive = game.players.filter(role='MAFIA', is_alive=True).count()
        civilians_alive = game.players.filter(role__in=['CIVILIAN', 'DOCTOR', 'COMMISSIONER'], is_alive=True).count()
        
        if mafia_alive == 0:
            game.status = 'FINISHED'
            game.end_time = timezone.now()
            game.save()
            messages.success(request, "Голосование завершено. Мирные жители победили!")
            return redirect('game_detail', game_id=game.id)
        elif mafia_alive >= civilians_alive:
            game.status = 'FINISHED'
            game.end_time = timezone.now()
            game.save()
            messages.success(request, "Голосование завершено. Мафия победила!")
            return redirect('game_detail', game_id=game.id)
        

        game.current_round += 1 
        game.save() 
        new_round_obj = Round.objects.create(
            game=game,
            round_number=game.current_round,
            phase='DAY', 
            events=f"Начался День {game.current_round}. " + "\n".join(events_log)
        )
        game.status = 'DAY'
        game.save()
        messages.success(request, f"Игра перешла в фазу 'День' Раунда {game.current_round}.")
        return redirect('game_detail', game_id=game.id)


    elif current_phase == 'DAY':

        new_phase_for_current_round = next_phase_in_round_map.get(current_phase) 
        current_round_obj.phase = new_phase_for_current_round
        game.status = new_phase_for_current_round 
        messages.success(request, f"Игра перешла в фазу '{new_phase_for_current_round}' Раунда {game.current_round}.")
        current_round_obj.events += "\n" + "\n".join(events_log) if events_log else ""
        current_round_obj.save()
        game.save()
        return redirect('game_detail', game_id=game.id)
    
    else:
        messages.error(request, "Неизвестная или некорректная текущая фаза для перехода.")
        return redirect('game_detail', game_id=game.id)


@login_required
@is_host_of_game
def start_voting(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    current_round_obj = get_object_or_404(Round, game=game, round_number=game.current_round)

    if game.status != 'DAY' or current_round_obj.phase != 'DAY':
        messages.error(request, "Голосование можно начать только в дневной фазе.")
        return redirect('game_detail', game_id=game.id)

    if request.method == 'POST':
        current_round_obj.phase = 'VOTING'
        current_round_obj.events += "\nНачалось голосование."
        current_round_obj.save()
        messages.success(request, "Фаза голосования началась.")
        return redirect('game_detail', game_id=game.id)
    
    context = {
        'game': game,
        'current_round': current_round_obj,
    }
    return render(request, 'game_api/start_voting_confirm.html', context)


@login_required
@is_host_of_game
def kill_player(request, game_id, player_id):
    game = get_object_or_404(Game, id=game_id)
    player_to_kill = get_object_or_404(Player, id=player_id, game=game)

    if not player_to_kill.is_alive:
        messages.warning(request, f"Игрок {player_to_kill.nickname} уже мертв.")
        return redirect('game_detail', game_id=game.id)
    
    if request.method == 'POST':
        player_to_kill.is_alive = False
        player_to_kill.save()
        messages.success(request, f"Игрок {player_to_kill.nickname} был убит.")
        return redirect('game_detail', game_id=game.id)

    context = {
        'game': game,
        'player_to_kill': player_to_kill,
    }
    return render(request, 'game_api/confirm_kill.html', context)

@login_required
@is_host_of_game
def revive_player(request, game_id, player_id):
    game = get_object_or_404(Game, id=game_id)
    player_to_revive = get_object_or_404(Player, id=player_id, game=game)

    if player_to_revive.is_alive:
        messages.warning(request, f"Игрок {player_to_revive.nickname} уже жив.")
        return redirect('game_detail', game_id=game.id)
    
    if request.method == 'POST':
        player_to_revive.is_alive = True
        player_to_revive.save()
        messages.success(request, f"Игрок {player_to_revive.nickname} был воскрешен.")
        return redirect('game_detail', game_id=game.id)

    context = {
        'game': game,
        'player_to_revive': player_to_revive,
    }
    return render(request, 'game_api/confirm_revive.html', context) 

@login_required
@is_host_of_game
def change_player_role(request, game_id, player_id):
    game = get_object_or_404(Game, id=game_id)
    player = get_object_or_404(Player, id=player_id, game=game)

    if request.method == 'POST':
        form = ChangePlayerRoleForm(request.POST, instance=player)
        if form.is_valid():
            form.save()
            messages.success(request, f"Роль игрока {player.nickname} изменена на {player.get_role_display()}.")
            return redirect('game_detail', game_id=game.id)
        else:
            messages.error(request, "Ошибка при изменении роли.")
    else:
        form = ChangePlayerRoleForm(instance=player)
    
    context = {
        'game': game,
        'player': player,
        'form': form,
    }
    return render(request, 'game_api/change_player_role.html', context)


@transaction.atomic
def submit_player_action(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    current_round_obj = get_object_or_404(Round, game=game, round_number=game.current_round)

    actor = None
    if request.user.is_authenticated:
        actor = Player.objects.filter(game=game, user=request.user, is_alive=True).first()
    elif 'player_id' in request.session and request.session.get('game_id') == game_id:
        try:
            actor = Player.objects.get(id=request.session['player_id'], game=game, is_alive=True)
        except Player.DoesNotExist:
            pass

    if not actor:
        messages.error(request, "Вы не являетесь активным игроком в этой игре или не авторизованы.")
        return redirect('game_detail', game_id=game.id)

    if not actor.is_alive:
        messages.warning(request, "Мертвые игроки не могут совершать действия.")
        return redirect('game_detail', game_id=game.id)

    if request.method == 'POST':

        form = PlayerActionForm(request.POST, game_id=game_id, current_player=actor, current_phase=current_round_obj.phase)
        
        if form.is_valid():
            action_type = form.cleaned_data['action_type']

            target_player_object = form.cleaned_data.get('target_player_id') 

            if target_player_object: 
                if not target_player_object.is_alive and action_type != 'DOCTOR_HEAL':
                    messages.error(request, "Вы не можете выбрать мертвую цель для этого действия (кроме доктора).")
                    return redirect('game_detail', game_id=game.id)
                if target_player_object == actor and action_type in ['MAFIA_KILL', 'COMMISSIONER_CHECK']:
                    messages.error(request, "Нельзя выбрать себя в качестве цели для этого действия.")
                    return redirect('game_detail', game_id=game.id)
            
            if PlayerAction.objects.filter(round=current_round_obj, actor=actor, action_type=action_type).exists():
                messages.warning(request, "Вы уже совершали это действие в текущей фазе.")
                return redirect('game_detail', game_id=game.id)
            PlayerAction.objects.create(
                round=current_round_obj,
                actor=actor,
                target=target_player_object, 
                action_type=action_type
            )
            messages.success(request, f"Действие '{actor.get_role_display()} - {action_type}' успешно отправлено.")
            return redirect('game_detail', game_id=game.id)
        else:

            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Ошибка в поле '{field}': {error}")
            messages.error(request, "Ошибка при отправке действия. Проверьте форму.")
            return redirect('game_detail', game_id=game.id)
    
    messages.error(request, "Недопустимый метод запроса для отправки действия.")
    return redirect('game_detail', game_id=game.id)

@login_required
@is_host_of_game
def remove_player_from_lobby(request, game_id, player_id):
    game = get_object_or_404(Game, id=game_id)
    player_to_remove = get_object_or_404(Player, id=player_id, game=game)


    if player_to_remove.is_host:
        messages.error(request, "Вы не можете удалить ведущего игры.")
        return redirect('game_lobby', game_id=game.id)

    if request.method == 'POST':
        player_to_remove.delete()
        game.players_count = game.players.count()
        game.save()
        messages.success(request, f"Игрок '{player_to_remove.nickname}' удален из лобби.")
        return redirect('game_lobby', game_id=game.id)
    
    messages.error(request, "Недопустимый метод запроса.")
    return redirect('game_lobby', game_id=game.id)


def search_game(request):
    games = Game.objects.order_by('-id')
    game = ''
    return render(request,'game_api/search_game.html',{"games":games})




















def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request,user)
            messages.success(request, "Вы успешно зарегистрированы и вошли в систему!")
            return redirect('profile')
        else:
            messages.error(request, "Ошибка регистрации. Пожалуйста, проверьте введенные данные.")
    else:
        form = UserCreationForm()
    return render(request, 'game_api/register.html',{'form':form})

def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username,password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Добро пожаловать, {username}")
                return redirect('profile')
            else:
                messages.error(request, "Неверное имя пользователя или пароль.")
        else:
            messages.error(request, "Неверное имя пользователя или пароль.")
    else:
        form = AuthenticationForm()
    return render(request, 'game_api/login.html', {'form': form})

@login_required
def user_logout(request):
    logout(request)
    messages.info(request,"Вы успешно вышли из системы.")
    return redirect('home')

@login_required
def profile(request):
    return render(request, 'game_api/profile.html')

@login_required
def profile_edit(request):
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request,"Ваш профиль успешно обновлён.")
            return redirect('profile')
        else:
            messages.error(request,"Ошибка обновления профиля. Пожалуйста, проверьте введенные данные.")
    else:
        form = UserUpdateForm(instance=request.user)
    return render(request, 'game_api/edit_profile.html', {'form': form})

@login_required
def profile_delete(request):
    if request.method == 'POST':
        request.user.delete()
        messages.success(request, "Ваш аккаунт успешно удалён.")
        return redirect('register')
    return render(request,'game_api/delete_accaunt.html')
