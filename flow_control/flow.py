""" Flow Control Xblock allows to evaluate a condition and based on the outcome
 either display the unit's content or take an alternative action """

import logging
import pkg_resources

from xblock.core import XBlock
from xblock.fragment import Fragment
from xblock.fields import Scope, Integer, String
from xblockutils.studio_editable import StudioEditableXBlockMixin
from xblock.validation import ValidationMessage
from courseware.model_data import ScoresClient
from opaque_keys.edx.keys import UsageKey


LOGGER = logging.getLogger(__name__)


def load(path):
    """Handy helper for getting resources from our kit."""
    data = pkg_resources.resource_string(__name__, path)
    return data.decode("utf8")


def _actions_generator(block):  # pylint: disable=unused-argument
    """ Generates a list of possible actions to
    take when the condition is met """

    return ['Display a message',
            'Redirect using jump_to_id',
            'Redirect to a given unit in the same subsection',
            'Redirect to a given URL'
            ]


def _conditions_generator(block):  # pylint: disable=unused-argument
    """ Generates a list of possible conditions to evaluate """
    return ['Grade of a problem',
            'Average grade of a list of problems']


def _operators_generator(block):  # pylint: disable=unused-argument
    """ Generates a list of possible operators to use """
    return ['equal to',
            'not equal to',
            'less than or equal to',
            'less than',
            'greater than or equal to',
            'greater than']


@XBlock.needs("i18n")
@XBlock.needs("user")
# pylint: disable=too-many-ancestors
class FlowCheckPointXblock(StudioEditableXBlockMixin, XBlock):
    """ FlowCheckPointXblock allows to take different
    learning paths based on a certain condition status """

    display_name = String(
        display_name="Display Name",
        scope=Scope.settings,
        default="Flow Control"
    )

    action = String(display_name="Action",
                    help="Select the action to be performed "
                    "when the condition is met",
                    scope=Scope.content,
                    default="Display a message",
                    values_provider=_actions_generator)

    condition = String(display_name="Flow control condition",
                       help="Select a conditon to evaluate",
                       scope=Scope.content,
                       default='Grade of a problem',
                       values_provider=_conditions_generator)

    operator = String(display_name="Comparison type",
                      help="Select an operator for the condition",
                      scope=Scope.content,
                      default='equal to',
                      values_provider=_operators_generator)

    ref_value = Integer(help="Enter the value to be used in "
                        "the comparison. (From 0 to 100)",
                        default=0,
                        scope=Scope.content,
                        display_name="Score percentage")

    tab_to = Integer(help="Number of unit tab to redirect to. (1, 2, 3...)",
                     default=1,
                     scope=Scope.content,
                     display_name="Tab to redirect to")

    target_url = String(help="URL to redirect to, supports relative "
                        "or absolute urls",
                        scope=Scope.content,
                        display_name="URL to redirect to")

    target_id = String(help="Unit identifier to redirect to (Location id)",
                       scope=Scope.content,
                       display_name="Unit identifier to redirect to")

    message = String(help="Message for the learners to view "
                     "when the condition is met",
                     scope=Scope.content,
                     default='',
                     display_name="Message",
                     multiline_editor='html')

    problem_id = String(help="Problem id to use for the condition.  (Not the "
                        "complete problem locator. Only the 32 characters "
                        "alfanumeric id. "
                        "Example: 618c5933b8b544e4a4cc103d3e508378)",
                        scope=Scope.content,
                        display_name="Problem id")

    list_of_problems = String(help="List of problems ids separated by commas "
                              "or line breaks. (Not the complete problem "
                              "locators. Only the 32 characters alfanumeric "
                              "ids. Example: 618c5933b8b544e4a4cc103d3e508378"
                              ", 905333bd98384911bcec2a94bc30155f). "
                              "The simple average score for all problems will "
                              "be used.",
                              scope=Scope.content,
                              display_name="List of problems",
                              multiline_editor=True,
                              resettable_editor=False)

    editable_fields = ('condition',
                       'problem_id',
                       'list_of_problems',
                       'operator',
                       'ref_value',
                       'action',
                       'tab_to',
                       'target_url',
                       'target_id',
                       'message')

    def validate_field_data(self, validation, data):
        """
        Validate this block's field data
        """

        if data.tab_to <= 0:
            validation.add(ValidationMessage(
                ValidationMessage.ERROR,
                u"Tab to redirect to must be greater than zero"))

        if data.ref_value < 0 or data.ref_value > 100:
            validation.add(ValidationMessage(
                ValidationMessage.ERROR,
                u"Score percentage field must "
                u"be an integer number between 0 and 100"))

    def get_location_string(self, locator):
        """  Returns the location string for one problem, given its id  """
        # pylint: disable=no-member
        course_prefix = 'course'
        resource = 'problem'
        course_url = self.course_id.to_deprecated_string()
        course_url = course_url.split(course_prefix)[-1]

        location_string = '{prefix}{couse_str}+{type}@{type_id}+{prefix}@{locator}'.format(
            prefix=self.course_id.BLOCK_PREFIX,
            couse_str=course_url,
            type=self.course_id.BLOCK_TYPE_PREFIX,
            type_id=resource,
            locator=locator)

        return location_string

    def get_condition_status(self):
        """  Returns the current condition status  """
        condition_reached = False
        problems = []

        if self.condition == 'Grade of a problem':
            problems = self.problem_id.split()

        if self.condition == 'Average grade of a list of problems':
            problems = self.list_of_problems.split()

        condition_reached = self.condition_on_problem_list(problems)

        return condition_reached

    def student_view(self, context=None):  # pylint: disable=unused-argument
        """  Returns a fragment for student view  """
        fragment = Fragment(u"<!-- This is the FlowCheckPointXblock -->")
        fragment.add_javascript(load("static/js/injection.js"))

        # helper variables
        # pylint: disable=no-member
        in_studio_runtime = hasattr(self.xmodule_runtime, 'is_author_mode')
        index_base = 1
        default_tab = 'tab_{}'.format(self.tab_to - index_base)

        fragment.initialize_js(
            'FlowControlGoto',
            json_args={"display_name": self.display_name,
                       "default": default_tab,
                       "default_tab_id": self.tab_to,
                       "action": self.action,
                       "target_url": self.target_url,
                       "target_id": self.target_id,
                       "message": self.message,
                       "in_studio_runtime": in_studio_runtime})

        return fragment

    @XBlock.json_handler
    def condition_status_handler(self, data, suffix=''):  # pylint: disable=unused-argument
        """  Returns the actual condition state  """

        return {
            'success': True,
            'status': self.get_condition_status()
        }

    def author_view(self, context=None):  # pylint: disable=unused-argument, no-self-use
        """  Returns author view fragment on Studio """
        # creating xblock fragment
        # TO-DO display for studio with setting resume
        fragment = Fragment(u"<!-- This is the studio -->")
        fragment.add_javascript(load("static/js/injection.js"))
        fragment.initialize_js('StudioFlowControl')

        return fragment

    def studio_view(self, context=None):
        """  Returns studio view fragment """
        fragment = super(FlowCheckPointXblock,
                         self).studio_view(context=context)

        # We could also move this function to a different file
        fragment.add_javascript(load("static/js/injection.js"))
        fragment.initialize_js('EditFlowControl')

        return fragment

    def compare_scores(self, correct, total):
        """  Returns the result of comparison using custom operator """
        result = False
        if total:
            # getting percentage score for that section
            percentage = (correct / total) * 100

            if self.operator == 'equal to':
                result = percentage == self.ref_value
            if self.operator == 'not equal to':
                result = percentage != self.ref_value
            if self.operator == 'less than or equal to':
                result = percentage <= self.ref_value
            if self.operator == 'greater than or equal to':
                result = percentage >= self.ref_value
            if self.operator == 'less than':
                result = percentage < self.ref_value
            if self.operator == 'greater than':
                result = percentage > self.ref_value

        return result

    def condition_on_problem_list(self, problems):
        """ Returns the score for a list of problems """
        # pylint: disable=no-member
        user_id = self.xmodule_runtime.user_id
        scores_client = ScoresClient(self.course_id, user_id)
        scores_reducible_length = 2
        total = 0
        correct = 0

        def _get_usage_key(problem):

            loc = self.get_location_string(problem)
            try:
                uk = UsageKey.from_string(loc)
            except Exception:
                uk = None
            return uk

        usages_keys = map(_get_usage_key, problems)
        scores_client.fetch_scores(usages_keys)
        scores = map(scores_client.get, usages_keys)
        scores = filter(None, scores)

        if scores and len(scores) >= scores_reducible_length:
            correct = reduce(lambda x, y: x.correct + y.correct, scores)
            total = reduce(lambda x, y: x.total + y.total, scores)
        if scores and len(scores) == 1:
            correct = scores[0].correct
            total = scores[0].total

        return self.compare_scores(correct, total)
