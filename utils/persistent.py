from commands.Partnership.partnershipSystem import PartnerRequestButtonView
from commands.Sigils.sigils import GiveawayEntryView, PersistentSigilsInfoView
from commands.Registration.registration import RegistrationDropdownView, RegistrationButtonView

from commands.CoOp.coOpSystem import CoOpButtonViewSystem
from commands.CoOp.coOpSystem import CoOpView as CoOpViewSystem
from commands.CoOp.coOpCelestial import CoOpButtonView as CoOpButtonViewCelestial
from commands.CoOp.coOpCelestial import CoOpView as CoOpViewCelestial
from commands.CoOp.coOpWuwaJinhsi import CoOpButtonViewWuwa
from commands.CoOp.coOpWuwaJinhsi import CoOpViewWuwa

from commands.Events.event import UserSelectView, PersistentChestInfoView, FeedbackView
from commands.Events.helperFunctions import PersistentXPQuestInfoView, TierRewardsView

from commands.Custom.celestial import RefreshStaffViewCelestial, LeaksAccessCelestial
from commands.Custom.levelUp import ShowPerksBulletin
from commands.Custom.fourCorners import GameAnnounceView

from shared.Tickets.tickets import CloseTicketButton, TicketAdminButtons, ConfirmCloseTicketButtons, CreateTicketButtonView, SelectView
from shared.Boosters.booster import AutoResponseApprovalView, RoleApprovalView

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
    FeedbackView,
    AutoResponseApprovalView,
    RoleApprovalView,
    PersistentXPQuestInfoView,
    GameAnnounceView,
    TierRewardsView,
    GiveawayEntryView,
    PersistentSigilsInfoView,
    RegistrationDropdownView,
    RegistrationButtonView,
    CloseTicketButton,
    TicketAdminButtons,
    ConfirmCloseTicketButtons,
    CreateTicketButtonView,
    SelectView,
]
