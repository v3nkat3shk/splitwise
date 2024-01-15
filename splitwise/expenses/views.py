from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken

from expenses.serializers import (
    UserSerializer, GetUserSerializer, ExpenseSerializer, IndividualExpenseSerializer,
    CreateExpenseSerializer, CreateUserSerializer)
from expenses.models import User, Expense, IndividualExpense, Type


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class CustomAuthToken(ObtainAuthToken):

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'email': user.email
        })


class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer


class IndividualExpenseViewSet(viewsets.ModelViewSet):
    queryset = IndividualExpense.objects.all()
    serializer_class = IndividualExpenseSerializer


class CreateExpense(GenericAPIView):
    """
    Create expenses
    """
    serializer_class = CreateExpenseSerializer

    def post(self, request, formt=None):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        payed_by = User.objects.filter(
            id=serializer.data.get('payed_by')).first()
        if not payed_by:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        individual_expenses = create_individual_expense(
            type=serializer.data.get('type'),
            participants=serializer.data.get(
                'participants') + [payed_by.pk],
            total_amount=serializer.data.get('total_amount'))

        Expense.objects.bulk_create([Expense(
            description=serializer.data.get('description'),
            total_amount=serializer.data.get('total_amount'),
            type=serializer.data.get('type'),
            individual_expenses=individual_expense,
            payed_by=payed_by)
            for individual_expense in individual_expenses])
        return Response(status=status.HTTP_201_CREATED)


def create_individual_expense(type, participants, total_amount, **kwargs):
    if type == Type.equal:
        individual_amount = total_amount / len(participants)
        participants = User.objects.filter(id__in=participants)
        individual_expenses = IndividualExpense.objects.bulk_create([IndividualExpense(
            user=participant,
            amount=individual_amount) for participant in participants])
        return individual_expenses
    elif type == Type.exact:
        payment_data = kwargs.get('participants_info')
        return IndividualExpense.objects.bulk_create([IndividualExpense(
            user__id=data.get('user_id'), amount=data.get('amount')) for data in payment_data])
    elif type == Type.percentage:
        payment_data = kwargs.get('participants_info')
        payment_data = [{"user_id": data.get("user_id"), "amount": amount_from_percent(
            data.get('percent'), total_amount)} for data in payment_data]
        return IndividualExpense.objects.bulk_create(
            [IndividualExpense(user=data.get('user_id'), amount=data.get('amount'))
             for data in payment_data]
        )


def amount_from_percent(percent, total_amount):
    individual_value = (percent / total_amount) * 100
    return individual_value


@api_view()
def user_expenses(request):
    """
    Get user expenses
    """
    user_id = request.query_params.get('user_id')
    user = User.objects.filter(id=user_id).first()
    if not user:
        return Response(status=status.HTTP_400_BAD_REQUEST)

    ind_exps = IndividualExpense.objects.filter(
        expense__paid_by=user).exclude(user=user)
    user_exps = IndividualExpense.objects.filter(
        expense__paid_by=ind_exps.values_list('user'), user=user)

    result_ind = {}
    result_user = {}

    ind_exps = [{"username": ind_exp.user.username,
                 "amount": ind_exp.amount} for ind_exp in ind_exps]
    user_exps = [{"username": user_exp.user.username,
                  "amount": user_exp.amount} for user_exp in user_exps]

    for exp in ind_exps:
        if result_ind.get(exp.get('username')):
            result_ind[exp.get('username')] += exp.get('amount')
        else:
            result_ind[exp.get('username')] = exp.get('amount')

    for exp in user_exps:
        if result_ind.get(exp.get('username')):
            result_ind[exp.get('username')] += exp.get('amount')
        else:
            result_ind[exp.get('username')] = exp.get('amount')


@api_view()
def user_balance(request):
    """
    Get balances for the user with option to simplify the balance
    """
    pass
