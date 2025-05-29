import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
import json
import os
import asyncio
import datetime
from keep_alive import keep_alive

# Konfiguracja intencji
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

intents = discord.Intents.default()
intents.members = True  # Wymagane do wykrywania nowych członków

bot = commands.Bot(command_prefix='!', intents=intents)

invite_uses = {}


@bot.event
async def on_ready():
    print(f'Zalogowano jako {bot.user}')
    for guild in bot.guilds:
        invites = await guild.invites()
        invite_uses[guild.id] = {
            invite.code: invite.uses
            for invite in invites
        }


class CustomHelpCommand(commands.HelpCommand):

    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot

        message = "Dostępne komendy:\n"
        for command in sorted(bot.commands, key=lambda x: x.name):
            message += f"!{command.name} - {command.help or 'Brak opisu'}\n"

        await ctx.send(f"```{message}```", delete_after=30)


bot = commands.Bot(command_prefix="!",
                   intents=intents,
                   help_command=CustomHelpCommand())

# ------ KONFIGURACJA ------
CHANNEL_ID_EMBED = 1374136622337228833
CHANNEL_ID_ORDERS = 1374136622337228836
ADMIN_CHANNEL_ID = 1374136622337228837
PUBLIC_CHANNEL_ID = 1374136622337228834
PUBLIC_CHANNEL_JEDNORAZOWKI_ID = 1374136622337228835
FLAVORS_FILE = 'flavors.json'
JEDNORAZOWKI_FILE = 'jednorazowki.json'

# ------ SYSTEM JEDNORAZÓWEK ------
if os.path.exists(JEDNORAZOWKI_FILE):
    with open(JEDNORAZOWKI_FILE, 'r', encoding='utf-8') as f:
        jednorazowki = json.load(f)
else:
    jednorazowki = []
    with open(JEDNORAZOWKI_FILE, 'w', encoding='utf-8') as f:
        json.dump(jednorazowki, f, ensure_ascii=False, indent=4)


def save_jednorazowki():
    with open(JEDNORAZOWKI_FILE, 'w', encoding='utf-8') as f:
        json.dump(jednorazowki, f, ensure_ascii=False, indent=4)


def generate_jednorazowki_message():
    if not jednorazowki:
        return "**Brak dostępnych jednorazówek**"
    return "**DOSTĘPNE JEDNORAZÓWKI:**\n" + "\n".join(
        f"{i}. {j}" for i, j in enumerate(jednorazowki, 1))


async def update_public_channel_jednorazowki():
    channel = bot.get_channel(PUBLIC_CHANNEL_JEDNORAZOWKI_ID)
    if channel:
        async for msg in channel.history(limit=10):
            if msg.author == bot.user:
                await msg.edit(content=generate_jednorazowki_message())
                return
        await channel.send(generate_jednorazowki_message())


@bot.command(name='j_dodaj', help="Dodaje smaki jednorazówek (przecinki)")
async def add_jednorazowka(ctx, *, text):
    if ctx.channel.id != ADMIN_CHANNEL_ID:
        return

    new = [j.strip() for j in text.replace('\n', '').split(',') if j.strip()]
    added = [j for j in new if j not in jednorazowki]
    istniejące = [j for j in new if j in jednorazowki]

    jednorazowki.extend(added)
    save_jednorazowki()

    resp = []
    if added:
        resp.append(f"Dodano: {len(added)}")
    if istniejące:
        resp.append(f"Pominięto: {len(istniejące)}")

    if resp:
        await ctx.send("\n".join(resp))
    await update_public_channel_jednorazowki()


# ------ SYSTEM LIQUIDÓW ------
if os.path.exists(FLAVORS_FILE):
    with open(FLAVORS_FILE, 'r', encoding='utf-8') as f:
        flavors = json.load(f)
else:
    flavors = []
    with open(FLAVORS_FILE, 'w', encoding='utf-8') as f:
        json.dump(flavors, f, ensure_ascii=False, indent=4)


def save_flavors():
    with open(FLAVORS_FILE, 'w', encoding='utf-8') as f:
        json.dump(flavors, f, ensure_ascii=False, indent=4)


def generate_flavors_message():
    if not flavors:
        return "**Brak dostępnych smaków**"
    return "**DOSTĘPNE SMAKI:**\n" + "\n".join(
        f"{i}. {f}" for i, f in enumerate(flavors, 1))


async def update_public_channel():
    channel = bot.get_channel(PUBLIC_CHANNEL_ID)
    if channel:
        async for msg in channel.history(limit=10):
            if msg.author == bot.user:
                await msg.edit(content=generate_flavors_message())
                return
        await channel.send(generate_flavors_message())


@bot.command(name='dodaj', help="Dodaje smaki liquidów (przecinki)")
async def add_flavor(ctx, *, text):
    if ctx.channel.id != ADMIN_CHANNEL_ID:
        return

    new = [f.strip() for f in text.replace('\n', '').split(',') if f.strip()]
    added = [f for f in new if f not in flavors]
    istniejące = [f for f in new if f in flavors]

    flavors.extend(added)
    save_flavors()

    resp = []
    if added:
        resp.append(f"Dodano: {len(added)}")
    if istniejące:
        resp.append(f"Pominięto: {len(istniejące)}")

    if resp:
        await ctx.send("\n".join(resp))
    await update_public_channel()


# ------ SYSTEM ZAMÓWIEŃ ------
class LiquidEntry:

    def __init__(self, smak, ilosc, moc, typ_nikotyny):
        self.smak = smak
        self.ilosc = ilosc
        self.moc = moc
        self.typ_nikotyny = typ_nikotyny


class ProductTypeView(View):

    def __init__(self, cart):
        super().__init__(timeout=300)  # Added timeout
        self.cart = cart

    @discord.ui.button(label="Liquid", style=discord.ButtonStyle.primary)
    async def liquid_button(self, interaction: discord.Interaction,
                            button: discord.ui.Button):
        modal = ZamowienieModal(self.cart, is_jednorazowka=False)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Jednorazówka",
                       style=discord.ButtonStyle.secondary)
    async def jednorazowka_button(self, interaction: discord.Interaction,
                                  button: discord.ui.Button):
        modal = ZamowienieModal(self.cart, is_jednorazowka=True)
        await interaction.response.send_modal(modal)


class ZamowienieModal(Modal):

    def __init__(self, cart, is_jednorazowka):
        super().__init__(title="Zamówienie")
        self.cart = cart
        self.is_jednorazowka = is_jednorazowka

        self.smak = TextInput(
            label="Smak jednorazówki" if is_jednorazowka else "Smak liquidu",
            placeholder="Wpisz smak...")
        self.add_item(self.smak)

    async def on_submit(self, interaction):
        try:
            if self.is_jednorazowka:
                entry = LiquidEntry(self.smak.value, "1", "0", "jednorazówka")
                self.cart.append(entry)
                view = OrderActionsView(self.cart)
                await interaction.response.send_message(
                    "✅ Jednorazówka dodana!", view=view, ephemeral=True)
            else:
                view = LiquidConfigView(self.cart, self.smak.value)
                await interaction.response.send_message(
                    "Wybierz parametry liquidu:", view=view, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Błąd: {str(e)}",
                                                    ephemeral=True)


class LiquidConfigView(View):

    def __init__(self, cart, smak):
        super().__init__(timeout=300)
        self.cart = cart
        self.smak = smak
        self.config = {}

    @discord.ui.select(placeholder="Typ nikotyny",
                       options=[
                           discord.SelectOption(label="Solna", value="solna"),
                           discord.SelectOption(label="Zasadowa",
                                                value="zasadowa")
                       ])
    async def type_select(self, interaction: discord.Interaction,
                          select: discord.ui.Select):
        self.config["type"] = select.values[0]
        await self.update_view(interaction)

    @discord.ui.select(placeholder="Wielkość",
                       options=[
                           discord.SelectOption(label="10ml", value="10"),
                           discord.SelectOption(label="60ml", value="60")
                       ])
    async def size_select(self, interaction: discord.Interaction,
                          select: discord.ui.Select):
        self.config["size"] = select.values[0]
        await self.update_view(interaction)

    @discord.ui.select(placeholder="Moc",
                       options=[
                           discord.SelectOption(label="6mg", value="6"),
                           discord.SelectOption(label="12mg", value="12"),
                           discord.SelectOption(label="18mg", value="18"),
                           discord.SelectOption(label="24mg", value="24"),
                           discord.SelectOption(label="36mg", value="36"),
                           discord.SelectOption(label="50mg", value="50")
                       ])
    async def strength_select(self, interaction: discord.Interaction,
                              select: discord.ui.Select):
        self.config["strength"] = select.values[0]
        await self.update_view(interaction)

    async def update_view(self, interaction):
        try:
            # Update strength options based on nicotine type
            if "type" in self.config:
                if self.config["type"] == "solna":
                    strength_options = [10, 15, 20, 25, 30]
                else:  # zasadowa
                    strength_options = [6, 12, 18, 24, 36, 50]

                # Update the strength select if it exists
                for item in self.children:
                    if hasattr(item,
                               'placeholder') and item.placeholder == "Moc":
                        item.options = [
                            discord.SelectOption(label=f"{m}mg", value=str(m))
                            for m in strength_options
                        ]
                        break

            # Check if all options are selected
            if len(self.config) == 3:
                entry = LiquidEntry(self.smak, self.config.get("size", ""),
                                    self.config.get("strength", ""),
                                    self.config.get("type", ""))
                self.cart.append(entry)
                view = OrderActionsView(self.cart)
                await interaction.response.edit_message(
                    content="✅ Liquid dodany!", view=view)
            else:
                await interaction.response.edit_message(view=self)
        except Exception as e:
            await interaction.response.send_message(f"❌ Błąd: {str(e)}",
                                                    ephemeral=True)


class OrderActionsView(View):

    def __init__(self, cart):
        super().__init__(timeout=300)
        self.cart = cart

    @discord.ui.button(label="➕ Dodaj kolejny",
                       style=discord.ButtonStyle.secondary)
    async def add_more(self, interaction: discord.Interaction,
                       button: discord.ui.Button):
        view = ProductTypeView(self.cart)
        await interaction.response.send_message("Wybierz typ produktu:",
                                                view=view,
                                                ephemeral=True)

    @discord.ui.button(label="🚀 Finalizuj", style=discord.ButtonStyle.primary)
    async def finalize(self, interaction: discord.Interaction,
                       button: discord.ui.Button):
        view = DeliverySelectionView(self.cart)
        await interaction.response.edit_message(
            content="🚚 Wybierz sposób dostawy:", view=view)


class DeliverySelectionView(View):

    def __init__(self, cart):
        super().__init__(timeout=300)
        self.cart = cart

    @discord.ui.select(placeholder="Sposób dostawy",
                       options=[
                           discord.SelectOption(label="Odbiór osobisty",
                                                value="osobisty"),
                           discord.SelectOption(label="Paczkomat",
                                                value="paczkomat")
                       ])
    async def delivery_select(self, interaction: discord.Interaction,
                              select: discord.ui.Select):
        delivery_type = select.values[0]
        if delivery_type == "osobisty":
            await interaction.response.send_modal(
                PersonalPickupModal(self.cart))
        else:
            await interaction.response.send_modal(
                ShippingDetailsModal(self.cart))


class PersonalPickupModal(Modal):

    def __init__(self, cart):
        super().__init__(title="Dane odbioru")
        self.cart = cart

        self.address = TextInput(label="Dzielnicę",
                                 required=True,
                                 placeholder="np Helenka")
        self.add_item(self.address)

    async def on_submit(self, interaction):
        try:
            view = PaymentView(self.cart, "osobisty",
                               {"address": self.address.value})
            await interaction.response.send_message(
                "💳 Wybierz metodę płatności:", view=view, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Błąd: {str(e)}",
                                                    ephemeral=True)


class ShippingDetailsModal(Modal):

    def __init__(self, cart):
        super().__init__(title="Dane wysyłki")
        self.cart = cart

        self.name = TextInput(label="Imię i nazwisko", required=True)
        self.email = TextInput(label="Email", required=True)
        self.phone = TextInput(label="Telefon", required=True)
        self.paczkomat = TextInput(label="Paczkomat", required=True)

        self.add_item(self.name)
        self.add_item(self.email)
        self.add_item(self.phone)
        self.add_item(self.paczkomat)

    async def on_submit(self, interaction):
        try:
            view = PaymentView(
                self.cart, "paczkomat", {
                    "name": self.name.value,
                    "email": self.email.value,
                    "phone": self.phone.value,
                    "paczkomat": self.paczkomat.value
                })
            await interaction.response.send_message(
                "💳 Wybierz metodę płatności:", view=view, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Błąd: {str(e)}",
                                                    ephemeral=True)


class PaymentView(View):

    def __init__(self, cart, delivery_type, shipping_details=None):
        super().__init__(timeout=300)
        self.cart = cart
        self.delivery_type = delivery_type
        self.shipping_details = shipping_details

    @discord.ui.button(label="📱 BLIK", style=discord.ButtonStyle.primary)
    async def blik_payment(self, interaction: discord.Interaction,
                           button: discord.ui.Button):
        await self.process_payment(interaction, "BLIK")

    @discord.ui.button(label="💵 Gotówka", style=discord.ButtonStyle.secondary)
    async def cash_payment(self, interaction: discord.Interaction,
                           button: discord.ui.Button):
        if self.delivery_type == "osobisty":
            await self.process_payment(interaction, "Gotówka")
        else:
            await interaction.response.send_message(
                "❌ Gotówka dostępna tylko przy odbiorze osobistym!",
                ephemeral=True)

    @discord.ui.button(label="❌ Anuluj", style=discord.ButtonStyle.danger)
    async def cancel_payment(self, interaction: discord.Interaction,
                             button: discord.ui.Button):
        await interaction.response.edit_message(
            content="❌ Zamówienie anulowane", view=None)

    async def process_payment(self, interaction, payment_method):
        try:
            preview = "**📝 PODSUMOWANIE ZAMÓWIENIA**\n\n"
            for i, item in enumerate(self.cart, 1):
                if item.typ_nikotyny == "jednorazówka":
                    preview += f"🍃 Jednorazówka {i}: {item.smak}\n"
                else:
                    preview += f"💧 Liquid {i}: {item.smak} ({item.ilosc}ml, {item.moc}mg, {item.typ_nikotyny})\n"

            preview += f"\n🚚 Dostawa: {'Odbiór osobisty' if self.delivery_type == 'osobisty' else 'Paczkomat'}"
            if self.shipping_details:
                if self.delivery_type == "osobisty":
                    preview += f"\n📍 Adres odbioru: {self.shipping_details.get('address', 'Brak danych')}"
                else:
                    preview += "\n📦 Dane wysyłki:"
                    for k, v in self.shipping_details.items():
                        preview += f"\n• {k}: {v}"

            preview += f"\n💳 Metoda płatności: {payment_method}"

            confirm_view = ConfirmationView(self.cart, self.delivery_type,
                                            self.shipping_details,
                                            payment_method)

            await interaction.response.edit_message(
                content=f"{preview}\n\n**⚠️ Sprawdź poprawność danych:**",
                view=confirm_view)
        except Exception as e:
            await interaction.response.send_message(f"❌ Błąd: {str(e)}",
                                                    ephemeral=True)


class OrderStatus:
    PENDING = "⏳ Oczekuje na potwierdzenie"
    CONFIRMED = "✅ Potwierdzone"
    SHIPPED = "🚚 Wysłane"
    DELIVERED = "📦 Dostarczone"


class ConfirmationView(View):

    def __init__(self, cart, delivery_type, shipping_details, payment_method):
        super().__init__(timeout=None)
        self.cart = cart
        self.delivery_type = delivery_type
        self.shipping_details = shipping_details
        self.payment_method = payment_method

        self.add_item(
            Button(label="✅ Potwierdź",
                   style=discord.ButtonStyle.success,
                   custom_id="confirm"))
        self.add_item(
            Button(label="❌ Anuluj",
                   style=discord.ButtonStyle.danger,
                   custom_id="cancel"))

    async def interaction_check(self, interaction):
        try:
            custom_id = interaction.data["custom_id"]

            if custom_id == "cancel":
                await interaction.response.edit_message(
                    content="❌ Zamówienie anulowane", view=None)
                return True

            if custom_id == "confirm":
                await self.process_order(interaction)
                return True

        except Exception as e:
            await interaction.response.send_message(f"❌ Błąd: {str(e)}",
                                                    ephemeral=True)
            return False

    async def process_order(self, interaction):
        try:
            orders_channel = bot.get_channel(CHANNEL_ID_ORDERS)
            chat_channel = bot.get_channel(
                1377693314542862417)  # New chat channel
            if not orders_channel or not chat_channel:
                await interaction.response.send_message(
                    "❌ Nie znaleziono wymaganych kanałów!", ephemeral=True)
                return

            # Count existing orders for order number
            order_count = 0
            async for message in orders_channel.history(limit=None):
                if message.embeds:
                    order_count += 1
            order_number = order_count + 1

            # Create order embed
            order_embed = discord.Embed(
                title=f"Zamówienie #{order_number}",
                description=f"**Status: {OrderStatus.PENDING}**",
                color=discord.Color.gold())

            # Add customer info
            order_embed.add_field(
                name="👤 Dane klienta",
                value=
                f"Użytkownik: {interaction.user.name} ({interaction.user.mention})\nID: {interaction.user.id}",
                inline=False)

            # Add items
            for idx, item in enumerate(self.cart, 1):
                if item.typ_nikotyny == "jednorazówka":
                    order_embed.add_field(name=f"Jednorazówka {idx}",
                                          value=f"Smak: {item.smak}",
                                          inline=False)
                else:
                    order_embed.add_field(
                        name=f"Liquid {idx}",
                        value=
                        f"Smak: {item.smak}\nIlość: {item.ilosc}ml\nMoc: {item.moc}mg\nTyp: {item.typ_nikotyny}",
                        inline=False)

            # Add delivery info
            order_embed.add_field(
                name="Dostawa",
                value=
                f"Typ: {'Odbiór osobisty' if self.delivery_type == 'osobisty' else 'Paczkomat'}",
                inline=False)

            # Add payment info
            order_embed.add_field(name="Płatność",
                                  value=self.payment_method,
                                  inline=False)

            # Add shipping details
            if self.shipping_details:
                if self.delivery_type == "osobisty":
                    order_embed.add_field(name="Adres odbioru",
                                          value=self.shipping_details.get(
                                              'address', 'Brak danych'),
                                          inline=False)
                else:
                    shipping_text = ""
                    for k, v in self.shipping_details.items():
                        shipping_text += f"{k}: {v}\n"
                    order_embed.add_field(name="Dane wysyłki",
                                          value=shipping_text.strip(),
                                          inline=False)

            order_embed.timestamp = discord.utils.utcnow()
            order_embed.set_footer(
                text=f"Zamówienie złożone przez {interaction.user.name}")

            # Create chat embed
            chat_embed = discord.Embed(
                title=f"Chat - Zamówienie #{order_number}",
                description="Historia wiadomości pojawi się tutaj",
                color=discord.Color.blue())
            chat_embed.add_field(
                name="👤 Klient",
                value=f"{interaction.user.name} ({interaction.user.mention})",
                inline=False)

            message = await interaction.channel.fetch_message(self.order_message_id)
            thread = await message.create_thread(name=f"Zamówienie #{order_number}")

# Zapisz ID wątku
            active_orders[order_number]["thread_id"] = thread.id

            # Create seller view
            seller_view = SellerOrderActionView(interaction.user.id)
            order_msg = await orders_channel.send(embed=order_embed,
                                                  view=seller_view)
            chat_msg = await chat_channel.send(embed=chat_embed)

            seller_view.order_message_id = order_msg.id
            seller_view.chat_message_id = chat_msg.id

            # Save message IDs in active_orders
            active_orders[str(order_number)] = {
                "customer_id": self.customer_id,
                "seller_id":
                interaction.guild.owner_id,  # Add seller ID (guild owner)
                "order_message_id": self.order_message_id,
                "chat_message_id": chat_msg.id,
                "channel_id": interaction.channel.id,
                "chat_channel_id": chat_channel.id,
		"thread_id": None,
                "messages": []
            }

            # Confirmation for customer
            await interaction.response.edit_message(
                content=
                "✅ Zamówienie zostało złożone! Oczekuj na potwierdzenie od sprzedawcy.",
                view=None)

            # Try to send DM to customer
            try:
                dm_embed = discord.Embed(
                    title=f"Zamówienie #{order_number} zostało złożone",
                    description=
                    "Twoje zamówienie zostało przyjęte. Oczekuj na potwierdzenie od sprzedawcy.",
                    color=discord.Color.blue())
                dm_embed.timestamp = discord.utils.utcnow()
                await interaction.user.send(embed=dm_embed)
            except Exception as e:
                print(f"Nie udało się wysłać DM do klienta: {e}")

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Błąd podczas przetwarzania zamówienia: {str(e)}",
                ephemeral=True)


# Słownik do przechowywania aktywnych zamówień
active_orders = {}
messages_db = {}


class MessageModal(Modal):

    def __init__(self, is_seller=False, recipient_id=None, order_number=None):
        super().__init__(title="Wyślij wiadomość")
        self.is_seller = is_seller
        self.recipient_id = recipient_id
        self.order_number = order_number
        self.message = TextInput(label="Twoja wiadomość",
                                 style=discord.TextStyle.paragraph,
                                 placeholder="Wpisz swoją wiadomość...",
                                 required=True)
        self.add_item(self.message)

    async def on_submit(self, interaction):
        try:
            sender_id = interaction.user.id

            # Find the order data
            order_data = None
            for order_num, data in active_orders.items():
                if (self.is_seller and data["customer_id"] == self.recipient_id) or \
                   (not self.is_seller and data["customer_id"] == sender_id):
                    order_data = data
                    self.order_number = order_num
                    break

            if not order_data:
                await interaction.response.send_message(
                    "❌ Nie znaleziono danych zamówienia.", ephemeral=True)
                return

            # Get chat channel and message
            chat_channel = bot.get_channel(order_data["chat_channel_id"])
            if not chat_channel:
                await interaction.response.send_message(
                    "❌ Nie znaleziono kanału czatu.", ephemeral=True)
                return

            chat_message = await chat_channel.fetch_message(
                order_data["chat_message_id"])

            # Add message to history
            new_message = {
                "sender_id": sender_id,
                "content": self.message.value,
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "is_seller": self.is_seller
            }

            order_data["messages"].append(new_message)

            # Update chat embed
            chat_embed = chat_message.embeds[0]

            # Create message history
            message_history = ""
            for msg in order_data["messages"][-10:]:  # Show last 10 messages
                sender_type = "👨‍💼 Sprzedawca" if msg[
                    "is_seller"] else "👤 Klient"
                timestamp = datetime.datetime.fromisoformat(
                    msg["timestamp"]).strftime("%H:%M")
                message_history += f"**{sender_type}** ({timestamp}):\n{msg['content']}\n\n"

            chat_embed.description = message_history if message_history else "Brak wiadomości"
            await chat_message.edit(embed=chat_embed)

            # Send notification to recipient
            try:
                recipient = await bot.fetch_user(
                    self.recipient_id if self.
                    is_seller else order_data["seller_id"])
                notification_embed = discord.Embed(
                    title=f"Nowa wiadomość - Zamówienie #{self.order_number}",
                    description=self.message.value,
                    color=discord.Color.blue())
                notification_embed.set_footer(
                    text=f"Od: {'Sprzedawcy' if self.is_seller else 'Klienta'}"
                )

                reply_view = View()
                reply_view.add_item(
                    Button(label="💬 Odpowiedz",
                           style=discord.ButtonStyle.primary,
                           custom_id=f"reply_{self.order_number}"))

                await recipient.send(embed=notification_embed, view=reply_view)
            except Exception as e:
                print(f"Nie udało się wysłać powiadomienia: {e}")

            await interaction.response.send_message(
                "✅ Wiadomość została wysłana!", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ Błąd: {str(e)}",
                                                    ephemeral=True)


# Update the on_interaction event to handle reply button
@bot.event
async def on_interaction(interaction):
    try:
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data["custom_id"]

            if custom_id == "order_button":
                view = ProductTypeView([])
                await interaction.response.send_message(
                    "📦 Wybierz typ produktu:", view=view, ephemeral=True)
            elif custom_id == "message_button":
                await interaction.response.send_modal(
                    MessageModal(is_seller=False))
            elif custom_id.startswith("reply_"):
                order_number = custom_id.split("_")[1]
                order_data = active_orders.get(order_number)

                if order_data:
                    is_seller = interaction.user.id != order_data[
                        "customer_id"]
                    recipient_id = order_data[
                        "customer_id"] if is_seller else order_data["seller_id"]

                    await interaction.response.send_modal(
                        MessageModal(is_seller=is_seller,
                                     recipient_id=recipient_id,
                                     order_number=order_number))
                else:
                    await interaction.response.send_message(
                        "❌ Nie znaleziono danych zamówienia.", ephemeral=True)
    except Exception as e:
        print(f"❌ Błąd interakcji: {str(e)}")
        await interaction.response.send_message(
            "❌ Wystąpił błąd podczas przetwarzania interakcji.",
            ephemeral=True)


# Update the init_system function to include the message button
async def init_system():
    try:
        channel = bot.get_channel(CHANNEL_ID_EMBED)
        if channel:
            await channel.purge(limit=5)
            embed = discord.Embed(
                title="🥤 Sklep Vape 🛒",
                description=
                "Kliknij poniżej aby złożyć zamówienie lub wysłać wiadomość",
                color=discord.Color.green())
            view = View()
            view.add_item(
                Button(label="🛒 ZAMÓW TERAZ",
                       style=discord.ButtonStyle.primary,
                       custom_id="order_button"))
            view.add_item(
                Button(label="💬 WYŚLIJ WIADOMOŚĆ",
                       style=discord.ButtonStyle.secondary,
                       custom_id="message_button"))
            await channel.send(embed=embed, view=view)

        await update_public_channel()
        await update_public_channel_jednorazowki()
        print("✅ Systemy zainicjalizowane")
    except Exception as e:
        print(f"❌ Błąd inicjalizacji: {str(e)}")


class SellerOrderActionView(View):

    def __init__(self, customer_id):
        super().__init__(timeout=None)
        self.customer_id = customer_id
        self.order_message_id = None
        self.chat_message_id = None
        self.add_item(
            Button(label="✅ Potwierdź zamówienie",
                   style=discord.ButtonStyle.success,
                   custom_id="seller_confirm"))

    async def interaction_check(self, interaction):
        try:
            custom_id = interaction.data["custom_id"]

            if custom_id == "seller_confirm":
                # Update order message
                message = await interaction.channel.fetch_message(
                    self.order_message_id)
                embed = message.embeds[0]
                embed.description = f"**Status: {OrderStatus.CONFIRMED}**"
                embed.color = discord.Color.green()

                # Create new view with shipping button
                shipping_view = SellerShippingView(self.customer_id,
                                                   self.order_message_id)
                await interaction.response.edit_message(embed=embed,
                                                        view=shipping_view)

                # Send DM to customer
                try:
                    customer = await bot.fetch_user(self.customer_id)
                    order_number = embed.title.split('#')[1]
                    dm_embed = discord.Embed(
                        title=
                        f"Zamówienie #{order_number} zostało potwierdzone",
                        description=
                        "Twoje zamówienie zostało potwierdzone przez sprzedawcę i jest przygotowywane.",
                        color=discord.Color.green())
                    dm_embed.timestamp = discord.utils.utcnow()
                    await customer.send(embed=dm_embed)
                except Exception as e:
                    print(f"Nie udało się wysłać DM do klienta: {e}")

                return True

        except Exception as e:
            await interaction.response.send_message(f"❌ Błąd: {str(e)}",
                                                    ephemeral=True)
            return False


class SellerShippingView(View):

    def __init__(self, customer_id, order_message_id):
        super().__init__(timeout=None)
        self.customer_id = customer_id
        self.order_message_id = order_message_id

        # We'll add buttons based on delivery type in interaction_check
        self.add_item(
            Button(label="💬 Wyślij wiadomość",
                   style=discord.ButtonStyle.secondary,
                   custom_id="send_message"))

    async def interaction_check(self, interaction):
        try:
            custom_id = interaction.data["custom_id"]

            # Get the order message
            message = await interaction.channel.fetch_message(
                self.order_message_id)
            if not message or not message.embeds:
                await interaction.response.send_message(
                    "❌ Nie można znaleźć danych zamówienia.", ephemeral=True)
                return False

            embed = message.embeds[0]
            order_number = embed.title.split('#')[1]

            # Check delivery type
            is_pickup = False
            for field in embed.fields:
                if field.name == "Dostawa" and "Odbiór osobisty" in field.value:
                    is_pickup = True
                    break

            if custom_id == "send_message":
                # Handle messaging
                await interaction.response.send_modal(
                    MessageModal(is_seller=True,
                                 recipient_id=self.customer_id))
                return True

            # Create new view based on delivery type
            new_view = View()
            new_view.add_item(
                Button(label="💬 Wyślij wiadomość",
                       style=discord.ButtonStyle.secondary,
                       custom_id="send_message"))

            if is_pickup:
                new_view.add_item(
                    Button(label="📦 Zamówienie gotowe do odebrania",
                           style=discord.ButtonStyle.primary,
                           custom_id="ready_for_pickup"))
            else:
                new_view.add_item(
                    Button(label="🚚 Oznacz jako wysłane",
                           style=discord.ButtonStyle.primary,
                           custom_id="mark_shipped"))

            # Update the message with appropriate view
            if interaction.message.components != new_view.to_components():
                await interaction.response.edit_message(view=new_view)
                return True

            if custom_id == "ready_for_pickup" and is_pickup:
                embed.description = "**Status: 📦 Gotowe do odebrania**"
                embed.color = discord.Color.blue()

                # Update the message
                await interaction.response.edit_message(embed=embed, view=None)

                # Send DM to customer
                try:
                    customer = await bot.fetch_user(self.customer_id)
                    dm_embed = discord.Embed(
                        title=
                        f"Zamówienie #{order_number} jest gotowe do odebrania",
                        description=
                        "Twoje zamówienie jest gotowe do odebrania. Kliknij przycisk poniżej, aby potwierdzić odbiór.",
                        color=discord.Color.blue())
                    dm_embed.timestamp = discord.utils.utcnow()

                    # Save order data
                    active_orders[order_number] = {
                        "customer_id": self.customer_id,
                        "order_message_id": self.order_message_id,
                        "channel_id": interaction.channel.id
                    }

                    delivery_confirm_view = CustomerDeliveryConfirmView(
                        order_number)
                    await customer.send(embed=dm_embed,
                                        view=delivery_confirm_view)
                    await interaction.followup.send(
                        "✅ Klient został powiadomiony.", ephemeral=True)
                except Exception as e:
                    print(f"Nie udało się wysłać DM do klienta: {e}")
                    await interaction.followup.send(
                        f"❌ Nie udało się wysłać powiadomienia do klienta: {str(e)}",
                        ephemeral=True)

            elif custom_id == "mark_shipped" and not is_pickup:
                embed.description = f"**Status: {OrderStatus.SHIPPED}**"
                embed.color = discord.Color.blue()

                await interaction.response.edit_message(embed=embed, view=None)

                try:
                    customer = await bot.fetch_user(self.customer_id)
                    dm_embed = discord.Embed(
                        title=f"Zamówienie #{order_number} zostało wysłane",
                        description=
                        "Twoje zamówienie zostało wysłane. Kliknij przycisk poniżej, aby potwierdzić odbiór.",
                        color=discord.Color.blue())
                    dm_embed.timestamp = discord.utils.utcnow()

                    active_orders[order_number] = {
                        "customer_id": self.customer_id,
                        "order_message_id": self.order_message_id,
                        "channel_id": interaction.channel.id
                    }

                    delivery_confirm_view = CustomerDeliveryConfirmView(
                        order_number)
                    await customer.send(embed=dm_embed,
                                        view=delivery_confirm_view)
                    await interaction.followup.send(
                        "✅ Klient został powiadomiony o wysyłce.",
                        ephemeral=True)
                except Exception as e:
                    print(f"Nie udało się wysłać DM do klienta: {e}")
                    await interaction.followup.send(
                        f"❌ Nie udało się wysłać powiadomienia do klienta: {str(e)}",
                        ephemeral=True)

            return True

        except Exception as e:
            await interaction.response.send_message(f"❌ Błąd: {str(e)}",
                                                    ephemeral=True)
            return False


class CustomerDeliveryConfirmView(View):

    def __init__(self, order_number):
        super().__init__(timeout=None)
        self.order_number = order_number
        self.add_item(
            Button(label="📦 Potwierdzam odbiór",
                   style=discord.ButtonStyle.success,
                   custom_id="confirm_delivery"))

    async def interaction_check(self, interaction):
        try:
            custom_id = interaction.data["custom_id"]

            if custom_id == "confirm_delivery":
                # Get order data
                if self.order_number not in active_orders:
                    await interaction.response.send_message(
                        "❌ Nie znaleziono informacji o tym zamówieniu.",
                        ephemeral=True)
                    return False

                order_data = active_orders[self.order_number]

                # Get channel and message
                channel = bot.get_channel(order_data["channel_id"])
                if not channel:
                    await interaction.response.send_message(
                        "❌ Nie znaleziono kanału zamówień.", ephemeral=True)
                    return False

                try:
                    message = await channel.fetch_message(
                        order_data["order_message_id"])

                    # Update embed
                    embed = message.embeds[0]
                    embed.description = f"**Status: {OrderStatus.DELIVERED}**"
                    embed.color = discord.Color.dark_green()

                    # Update view (no buttons)
                    await message.edit(embed=embed, view=None)

                    # Confirmation for customer
                    await interaction.response.edit_message(
                        content=
                        "✅ Dziękujemy za potwierdzenie odbioru! Miłego użytkowania produktów.",
                        embed=None,
                        view=None)

                    # Remove order from active orders
                    active_orders.pop(self.order_number, None)

                    return True
                except Exception as e:
                    print(f"Błąd podczas aktualizacji zamówienia: {e}")
                    await interaction.response.send_message(
                        f"❌ Wystąpił błąd: {str(e)}", ephemeral=True)
                    return False

        except Exception as e:
            await interaction.response.send_message(f"❌ Błąd: {str(e)}",
                                                    ephemeral=True)
            return False
@bot.event
async def on_message(message):
    if message.guild is not None or message.author.bot:
        return  # tylko DM i nie bot

    # Znajdź zamówienie klienta
    for order_number, data in active_orders.items():
        if data["customer_id"] == message.author.id:
            # Pobierz kanał i wątek
            thread = None
            if data.get("thread_id"):
                thread = bot.get_channel(data["thread_id"])

            if not thread:
                # Spróbuj znaleźć wiadomość i utworzyć wątek ponownie
                channel = bot.get_channel(data["channel_id"])
                try:
                    order_msg = await channel.fetch_message(data["order_message_id"])
                    thread = await order_msg.create_thread(name=f"Zamówienie #{order_number}")
                    data["thread_id"] = thread.id
                except Exception as e:
                    print(f"Nie udało się utworzyć wątku: {e}")
                    return

            # Prześlij wiadomość klienta do wątku
            await thread.send(
                content=f"📨 Wiadomość od klienta <@{message.author.id}>:\n{message.content}"
            )

            # Opcjonalnie: potwierdź klientowi, że wiadomość została przekazana
            await message.channel.send("📬 Twoja wiadomość została przekazana do zespołu.")
            break

# Uruchomienie bota
if __name__ == "__main__":
    keep_alive()  # Uruchom serwer keep_alive
    TOKEN = "MTM3NzYyNjU0MTA4MDU3NjAyMA.G6_ozA.AHbGsUlog_ZPTUilshJXf6j3bA-086NsDd5svk"  # Zmieniono dla bezpieczeństwa
    bot.run(TOKEN)
