from django.db import models
from django.contrib.auth.models import User 














class Game(models.Model):
    STATUS_CHOICES = [
        ('LOBBY', 'Лобби'),
        ('DAY', 'День'),
        ('NIGHT', 'Ночь'),
        ('VOTING', 'Голосование'),
        ('FINISHED', 'Завершена'),
    ]
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_games')
    status = models.CharField('Стаутус игры',max_length=10, choices=STATUS_CHOICES, default='LOBBY')
    players_count = models.IntegerField('Общее количество игроков',default=0)
    mafia_count = models.IntegerField('Общее количество мафии',default=0)
    doctor_count = models.IntegerField('Общее количество докторов',default=0)
    commissioner_count = models.IntegerField('Общее количество шерифов',default=0)
    current_round = models.IntegerField('Текущий номер хода(0-Лобби,1-День,2-Ночь...)',default=0)
    creation_time = models.DateTimeField('Дата и время создания игры',auto_now_add=True)
    start_time = models.DateTimeField('Время старта игры',null=True, blank=True)
    end_time = models.DateTimeField('Время завершения игры',null=True, blank=True)

    def __str__(self):
        return f"Игра #{self.id} (Ведущий: {self.host.username}, Статус: {self.status})"

    def get_alive_players(self):
        return self.players.filter(is_alive=True)

    def get_alive_mafia(self):
        return self.players.filter(is_alive=True, role='MAFIA')

    def get_absolute_url(self):
        return ''

    class Meta:
        verbose_name = 'Игра'
        verbose_name_plural = 'Игры'














class Player(models.Model):
    ROLE_CHOICES = [
        ('CIVILIAN', 'Мирный житель'),
        ('MAFIA', 'Мафия'),
        ('DOCTOR', 'Доктор'),
        ('COMMISSIONER', 'Комиссар'),
    ]
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='players')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='mafia_player_profiles') # Если игрок зарегистрирован
    nickname = models.CharField('Никнейм',max_length=50)
    role = models.CharField('Роль',max_length=15, choices=ROLE_CHOICES)
    is_alive = models.BooleanField('Жив ли игрок',default=True)
    is_host = models.BooleanField('Является ли игрок ведущим',default=False) 
    order_in_game = models.IntegerField('Порядок нумерации игрока в игре',default=0)
    class Meta:
        unique_together = ('game', 'nickname')

    def __str__(self):
        return f"{self.nickname} в игре #{self.game.id}"
        # return f"{self.nickname} ({self.role}) в игре #{self.game.id}" # более подробная информация

    def kill(self):
        self.is_alive = False
        self.save()

    def heal(self):
        self.is_alive = True 
        self.save()

    def get_absolute_url(self):
        return 'player/'

    class Meta:
        verbose_name = 'Игрок'
        verbose_name_plural = 'Игроки'









class Round(models.Model):
    PHASE_CHOICES = [
        ('NIGHT', 'Ночь'),
        ('DAY', 'День'),
        ('VOTING', 'Голосование'),
    ]
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='rounds')
    round_number = models.IntegerField('Номер хода')
    phase = models.CharField('Фаза(День,ночь,голосование)',max_length=10, choices=PHASE_CHOICES)
    mafia_kill_target = models.ForeignKey(
        'Player', on_delete=models.SET_NULL, null=True, blank=True, related_name='killed_in_round'
    )
    doctor_heal_target = models.ForeignKey(
        'Player', on_delete=models.SET_NULL, null=True, blank=True, related_name='healed_in_round'
    )
    commissioner_check_target = models.ForeignKey(
        'Player', on_delete=models.SET_NULL, null=True, blank=True, related_name='checked_in_round'
    )
    executed_player = models.ForeignKey(
        'Player', on_delete=models.SET_NULL, null=True, blank=True, related_name='executed_in_round'
    )
    events = models.TextField('Описание событий этого раунда',blank=True) 

    class Meta:
        unique_together = ('game', 'round_number')
        ordering = ['round_number'] 

    def __str__(self):
        return f"Ход {self.round_number} ({self.phase}) в игре #{self.game.id}"

    def get_absolute_url(self):
        return 'game/round/'

    class Meta:
        verbose_name = 'Раунд'
        verbose_name_plural = 'Раунды'




class PlayerAction(models.Model):
    ACTION_TYPES = [
        ('VOTE', 'Голосование'),
        ('MAFIA_KILL', 'Убийство мафии'),
        ('DOCTOR_HEAL', 'Лечение доктора'),
        ('COMMISSIONER_CHECK', 'Проверка комиссара'),
    ]
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='actions')
    actor = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='performed_actions')
    target = models.ForeignKey('Player', on_delete=models.SET_NULL, null=True, blank=True, related_name='targeted_actions')
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.actor.nickname} {self.action_type} -> {self.target.nickname if self.target else 'Никого'} в ходу {self.round.round_number}"

    def get_absolute_url(self):
        return 'game/'

    class Meta:
        verbose_name = 'Событие'
        verbose_name_plural = 'События'

