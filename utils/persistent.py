from commands.CoOp.coOpCelestial import CoOpButtonView as CoOpButtonViewCelestial
from commands.CoOp.coOpCelestial import CoOpView as CoOpViewCelestial
from commands.CoOp.coOpSystem import CoOpButtonViewSystem
from commands.CoOp.coOpSystem import CoOpView as CoOpViewSystem
from commands.CoOp.coOpWuwaJinhsi import CoOpButtonViewWuwa, CoOpViewWuwa
from commands.Custom.celestial import LeaksAccessCelestial, RefreshStaffViewCelestial
from commands.Custom.levelUp import ShowPerksBulletin
from commands.Events.chests import PersistentChestInfoView
from commands.Events.games.double import UserSelectView
from commands.Events.helperFunctions import TierRewardsView
from commands.Partnership.partnershipSystem import PartnerRequestButtonView
from commands.Utility.topic import TopicAcceptRejectView
from shared.Tickets.tickets import (
    CloseTicketButton,
    ConfirmCloseTicketButtons,
    CreateTicketButtonView,
    SelectView,
    TicketAdminButtons,
)

views = [
    CoOpButtonViewSystem,
    CoOpViewSystem,
    CoOpButtonViewCelestial,
    CoOpViewCelestial,
    LeaksAccessCelestial,
    RefreshStaffViewCelestial,
    CoOpButtonViewWuwa,
    CoOpViewWuwa,
    UserSelectView,
    ShowPerksBulletin,
    PartnerRequestButtonView,
    PersistentChestInfoView,
    TierRewardsView,
    CloseTicketButton,
    TicketAdminButtons,
    ConfirmCloseTicketButtons,
    CreateTicketButtonView,
    SelectView,
    TopicAcceptRejectView,
]
