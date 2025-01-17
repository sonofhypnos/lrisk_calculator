from functools import cache
import math
import pdb

import yaml

import runtime_constants as constant
from graph_functions import sigmoid_curved_risk, exponentially_decaying_risk

# This script prints out a series of probabilities for transition becoming interstellar based on
# estimates of the transition probabilities of various(values are currently hardcoded placeholders)
# states, as in a Markov chain. The states are extinction, survival, preindustrial, industrial, time
# of perils, multiplanetary, and interstellar.
#
# A full description/explanation of the model is in the section titled The Cyclical Model in this
# post:
# https://forum.effectivealtruism.org/posts/YnBwoNNqe6knBJH8p/modelling-civilisation-after-a-catastrophe#The_cyclical_model

## Transition probabilities from multiplanetary state

with open('params.yml', 'r') as stream:
  PARAMS = yaml.safe_load(stream)['multiplanetary']

@cache
def extinction_given_multiplanetary(q):
  return parameterised_decaying_transition_probability('extinction', q=q)

def survival_given_multiplanetary():
  """Sum of total survival exit probability over all values of q. Returns 0 on default values"""
  return parameterised_decaying_transition_probability('survival')

def preindustrial_given_multiplanetary():
  """Sum of total preindustrial exit probability over all values of q. Returns 0 on default values"""
  return parameterised_decaying_transition_probability('preindustrial')

def industrial_given_multiplanetary():
  """Sum of total industrial exit probability over all values of q. Returns 0 on default values"""
  return parameterised_decaying_transition_probability('industrial')

@cache
def interstellar_given_multiplanetary(q):
  """Max value should get pretty close to 1, since at a certain number of planets the tech is all
  necessarily available and you've run out of extra planets to spread to.

  TODO need to specify behaviour for max value."""

  def x_stretch():
    return PARAMS['interstellar']['x_stretch'] # Just intuition

  def y_stretch():
    # TODO - if this asymptotes too fast, we might get invalid total probabilities. Is there a neat
    # way to guard against that?
    return PARAMS['interstellar']['y_stretch']

  def x_translation():
    return PARAMS['interstellar']['x_translation']

  def sharpness():
    return PARAMS['interstellar']['sharpness']

  # Graph with these values: https://www.desmos.com/calculator/vdyih29fqb
  return sigmoid_curved_risk(q, x_stretch(), y_stretch(), x_translation(), sharpness())

@cache
def parameterised_decaying_transition_probability(target_state, q=None):
  if PARAMS[target_state]['two_planet_risk'] == 0:
    return 0

  @cache
  def starting_value(target_state):
    return PARAMS[target_state]['two_planet_risk']

  @cache
  def decay_rate(target_state):
    return PARAMS[target_state]['decay_rate']

  @cache
  def min_risk(min_risk):
    return PARAMS[target_state]['min_risk']

  @cache
  def x_translation(min_risk):
    return PARAMS[target_state]['x_translation']

  return exponentially_decaying_risk(
    x=q,
    starting_value=starting_value(target_state),
    decay_rate=decay_rate(target_state),
    min_probability=min_risk(target_state),
    x_translation=x_translation(target_state))

@cache
def transition_to_n_planets_given_multiplanetary(q, n):
  """Should be a value between 0 and 1. Lower treats events that could cause regression to a
  1-planet civilisation in a perils state as having their probability less reduced by having
  multiple settlements.

  On the inside view it seems like the decay rate could be either a) higher than for extinction,
  since late-development AI seems like the main extinction risk at this stage, and that might be as
  able to destroy multiple settlements as it is one, or b) lower than for extinction, since AI risk
  seems like it would peak early and then rapidly decline if it doesn't kill us almost immediately.

  On the outside view, it seems like it should be slightly lower, since a multiplanetary
  civilisation provides less evidence against the probability of regressing to perils than it does
  against the probability of going extinct.

  So on balance I err towards making it slightly lower.
  """
  N_PARAMS = PARAMS['n_planets']

  def any_intra_multiplanetary_regression(q):
    return exponentially_decaying_risk(x=q,
                                       starting_value=N_PARAMS['two_planet_risk'],
                                       decay_rate=N_PARAMS['decay_rate'],
                                       x_translation=N_PARAMS['x_translation'],
                                       min_probability=N_PARAMS['min_risk'])

  def remainder_outcome(q):
    extinction_given_multiplanetary(q)
    survival_given_multiplanetary()
    preindustrial_given_multiplanetary()
    industrial_given_multiplanetary()
    any_intra_multiplanetary_regression(q)
    interstellar_given_multiplanetary(q)
    return 1 - (extinction_given_multiplanetary(q)
                + survival_given_multiplanetary()
                + preindustrial_given_multiplanetary()
                + industrial_given_multiplanetary()
                + any_intra_multiplanetary_regression(q)
                + interstellar_given_multiplanetary(q)) # perils_given_multiplanetary is
                                                        # implicitly included as
                                                        # any_intra_multiplanetary_regression to
                                                        # n = 1

  def min_risk():
    return N_PARAMS['min_risk']

  if not n:
    # Allows us to check total probability sums to 1
    # TODO this branch prob obsolete now
    return any_intra_multiplanetary_regression(q)
  elif n == q + 1:
    # This is our catchall branch - the probability is whatever's left after we decide all the other
    # risks
    return remainder_outcome(q)

  elif n == q and q == constant.MAX_PLANETS:
    # For simplicity, when we hit max planets, we allow looping, and make that our remainder probability
    return remainder_outcome(q)

  elif n >= q:
    # We're only interested in changes to number of planets, and assume we can add max 1 at a time
    return 0
  else:
    # The commented return value describes the linear decrease described above
    # Uncomment the next two lines if you think this is a more reasonable treatment
    # return any_intra_multiplanetary_regression(q) * ((n + 1)
    #                                               / (1 + (q ** 2)/2 + 3 * q / 2))
    # The commented out return values is the exponential decrease described above. TODO - where?
    total_probability_of_loss = any_intra_multiplanetary_regression(q) # How likely is it in total
    # we lose any number of planets between 1 and (q - 1) inclusive?
    geometric_base = N_PARAMS['geometric_base']

    numerator_for_n_planets = geometric_base ** n # How relatively likely is it, given
    # some loss, that that loss took us to exactly n planets?
    # TODO - see if this still matches intuitions
    geometric_sum_of_weightings = geometric_base * (1 - geometric_base ** (q - 1)) / (1 - geometric_base)
    # Thus numerator_for_n_planets / geometric_sum_of_weightings is a proportion; you can play with
    # the values at https://www.desmos.com/calculator/ku0p2iahq3
    return total_probability_of_loss * (numerator_for_n_planets / geometric_sum_of_weightings)
                                       # Brackets seem to improve floating point errors at least
                                       # when the contents should be 1

@cache
def perils_given_multiplanetary(q):
  """Ideally this would have a more specific notion of where in a time of perils you expect to end
  up given this transition, but since that could get complicated fast, I'm treating it as going to
  perils year 0 for now.

  Since perils is basically defined as 'modern+ technology but with only 1 planet', we can just use
  the existing formula for this.

  TODO if going to a fixed perils year, make it a later one."""
  return transition_to_n_planets_given_multiplanetary(q, 1)



# exit_probabilities = [extinction_given_multiplanetary(1,11),
#                         survival_given_multiplanetary(1,11),
#                         preindustrial_given_multiplanetary(1,11),
#                         industrial_given_multiplanetary(1,11),
#                         perils_given_multiplanetary(1,11),
#                         interstellar_given_multiplanetary(1,11)]

# intra_transition_probabilities = [transition_to_n_planets_given_multiplanetary(1, 11, n) for n in range(2,21)]

# row = exit_probabilities + intra_transition_probabilities
# # transition_to_n_planets_given_multiplanetary(1, 9, 3)


# pdb.set_trace()


# TODO - consider reintroducing this checksum
# if not 1 == (extinction_given_multiplanetary(k)
#              + survival_given_multiplanetary(k)
#              + preindustrial_given_multiplanetary(k)
#              + industrial_given_multiplanetary(k)
#              + perils_given_multiplanetary(k)
#              + interstellar_given_multiplanetary(k)):
#   raise InvalidTransitionProbabilities("Transition probabilities from multiplanetary must == 1")
