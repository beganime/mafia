from django import forms
from django.contrib.auth.models import User
from django.forms import ModelForm, Form, TextInput, NumberInput, CharField
from .models import Game, Player, PlayerAction

class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']


class GameSettingsForm(ModelForm):
    class Meta:
        model = Game
        fields = ['players_count', 'mafia_count', 'doctor_count', 'commissioner_count']
        labels = {
            'players_count': 'Общее количество игроков',
            'mafia_count': 'Количество мафий',
            'doctor_count': 'Количество докторов',
            'commissioner_count': 'Количество комиссаров',
        }
        widgets = {
            "players_count": NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Введите общее количество игроков"
            }),
            "mafia_count": NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Введите общее количество Мафии"
            }),
            "doctor_count": NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Введите общее количество Докторов"
            }),
            "commissioner_count": NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Введите общее количество Комиссаров"
            })
        }
class AddPlayerForm(Form):
    nickname = CharField(max_length=50, label="Никнейм игрока")

class ChangePlayerRoleForm(ModelForm):
    class Meta:
        model = Player
        fields = ['role']
        labels = {
            'role': 'Новая роль',
        }



class JoinGameForm(forms.Form):
    game_id = forms.IntegerField(label="ID игры", widget=forms.NumberInput(attrs={
        "class": "id_game",
        "placeholder": "Введите ID игры"
    }))
    nickname = forms.CharField(max_length=50, label="Ваш никнейм", widget=forms.TextInput(attrs={
        "class": ".id_game",
        "placeholder": "Введите ваш никнейм"
    }))

class PlayerActionForm(forms.Form):
    action_type = forms.ChoiceField(
        choices=PlayerAction.ACTION_TYPES,
        label="Тип действия",
        widget=forms.Select(attrs={'class': 'game-form-control'}) 
    )
    target_player_id = forms.ModelChoiceField(
        queryset=Player.objects.all(),
        required=False,
        label="Цель действия (игрок)",
        widget=forms.Select(attrs={"class": 'game-form-control'})
    )

    def __init__(self, *args, **kwargs):
        game_id = kwargs.pop('game_id', None)
        current_player = kwargs.pop('current_player', None)
        current_phase = kwargs.pop('current_phase', None)
        super().__init__(*args, **kwargs)

        if game_id and current_player and current_phase:
            self.fields['target_player_id'].queryset = Player.objects.filter(game_id=game_id, is_alive=True).exclude(id=current_player.id)
            
            available_actions = []
            if current_phase == 'NIGHT':
                if current_player.role == 'MAFIA':
                    available_actions.append(('MAFIA_KILL', 'Убить игрока'))
                elif current_player.role == 'DOCTOR':
                    available_actions.append(('DOCTOR_HEAL', 'Вылечить игрока'))
                elif current_player.role == 'COMMISSIONER':
                    available_actions.append(('COMMISSIONER_CHECK', 'Проверить игрока'))
            elif current_phase == 'VOTING':
                available_actions.append(('VOTE', 'Проголосовать'))
            
            if not available_actions:
                self.fields['action_type'].choices = [('', 'Действий нет')]
                self.fields['target_player_id'].queryset = Player.objects.none()
                self.fields['target_player_id'].required = False
            else:
                self.fields['action_type'].choices = [('', 'Выберите действие')] + available_actions
                if current_player.role == 'DOCTOR' and current_phase == 'NIGHT':
                    self.fields['target_player_id'].queryset = Player.objects.filter(game_id=game_id, is_alive=True) # Исключаем только мертвых
                else:
                    self.fields['target_player_id'].queryset = Player.objects.filter(game_id=game_id, is_alive=True).exclude(id=current_player.id)
                if available_actions and available_actions[0][0] in ['MAFIA_KILL', 'DOCTOR_HEAL', 'COMMISSIONER_CHECK', 'VOTE']:
                    self.fields['target_player_id'].required = True
                else:
                    self.fields['target_player_id'].required = False


    def clean(self):
        cleaned_data = super().clean()
        action_type = cleaned_data.get('action_type')
        target_player_id = cleaned_data.get('target_player_id')

        if action_type in ['MAFIA_KILL', 'DOCTOR_HEAL', 'COMMISSIONER_CHECK', 'VOTE'] and not target_player_id:
            self.add_error('target_player_id', "Для этого действия необходимо выбрать цель.")
        
        return cleaned_data
