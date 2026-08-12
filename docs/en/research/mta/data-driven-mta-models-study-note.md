---
title: Data-Driven MTA Models Study Notes
compact: "Personal reading notes on the Data-driven Multi-touch Attribution Models paper: bagged logistic regression versus a simple probabilistic model, the A-metric and V-metric stability measures, sigmoid and log loss derivations. Neither model is implemented here; not a source of code facts."
lang: en-US
---

# Introduction

> Personal study note: this page summarizes a research paper and is not a description of the project's implemented Markov and path-level Shapley models. Use the [current attribution documentation](../../attribution/) for code facts.

For multi-touch attribution (MTA), stability is especially important because the attribution model determines the performance measure used to judge an advertising Campaign. Unlike an ordinary predictive-model use case, the primary purpose here is interpretation of contribution rather than prediction alone.

Attribution models fall into two broad families:

- Single-touch attribution: first-touch and last-touch attribution.
- Multi-touch attribution (MTA): linear, time-decay, position-based, Markov-chain, Shapley-value, bagged-logistic-regression, and probabilistic models.

Advertising tactics are judged through measures defined by the attribution model. The paper summarized by this note compares two MTA approaches: bagged logistic regression and a simple probabilistic model.

## Prerequisites

### V-Metric and A-Metric

For both bagged and ordinary logistic regression, the procedure samples from the population, uses part as training data and part as testing data, and repeats the experiment `S` times. Each experiment has its own sampling, training, testing, and V-/A-metric calculation.

#### A-Metric

The A-metric represents accuracy: can the model classify users correctly as:

- positive users who converted;
- negative users who did not convert?

For the two models in the note, the A-metric uses misclassification error rate:

$$
A=\frac{1}{S}\sum_{s=1}^{S}\operatorname{error}_s
$$

`S` is the number of repeated experiments and `error_s` is the classification error on experiment `s`'s test set.

#### V-Metric

The V-metric represents variance or stability. If Google's coefficient is 2.1 in the first training run, 0.8 in the second, and 3.5 in the third, its estimated contribution is unstable. With `p` channels and `S` experiments, the note expresses the metric as:

$$
V=\frac{1}{p}\sum_{i=1}^{p}\operatorname{SD}(x_i)
$$

where `SD(x_i)` is the standard deviation of a channel's coefficient across runs.

### Logistic Regression Model

Logistic regression is a common classification model used to predict whether an outcome occurs. For example:

For a Facebook ad → Google search → Email path, the model might output a conversion probability of 0.72.

Ordinary linear regression is:

$$
y=\beta_0+\beta_1x_1+\beta_2x_2+\beta_3x_3+\cdots
$$

Its output may be any number, whereas a conversion probability must remain between zero and one. Logistic regression first calculates:

$$
z=\beta_0+\beta_1x_1+\beta_2x_2+\beta_3x_3+\cdots
$$

and applies the sigmoid function:

$$
p=\frac{1}{1+e^{-z}}
$$

The resulting `p` lies in `[0,1]`; `p = 0.8` means an estimated 80% probability.

The study note decomposes training as follows.

**Step 1: data.** Sample training and test records from the population and fit on training data.

| User | Facebook | Google | Email | Converted |
| --- | ---: | ---: | ---: | ---: |
| User 1 | 1 | 1 | 0 | 1 |
| User 2 | 0 | 1 | 1 | 1 |
| User 3 | 1 | 0 | 0 | 0 |
| User 4 | 0 | 0 | 1 | 0 |

Facebook, Google, and Email are independent variables; conversion is the dependent variable.

**Step 2: initialize coefficients.** Before learning channel effects, begin with coefficient values such as:

For example, initialization may use $\beta_0=0$ and $\beta_1=\beta_2=\beta_3=0.1$.

**Step 3: calculate predicted probability.** Calculate `z`, then the sigmoid `p`. A predicted `p = 0.75` for User 1 means a 75% predicted conversion probability.

**Step 4: calculate prediction error.** Compare probability `p` with observed result `y`. If `y = 1`, `p = 0.2` is poor and `p = 0.9` is better. Logistic regression commonly uses log loss/cross-entropy:

$$
\mathcal{L}=-\left[y\log(p)+(1-y)\log(1-p)\right]
$$

**Step 5: update coefficients.** Adjust the `β` values to reduce loss, commonly with gradient descent: move parameters incrementally in the direction that reduces error fastest.

The final direct output is a probability.

## Two MTA Models

### Bagged Logistic Regression Model

Bagging means Bootstrap Aggregating: draw many random training samples from the original data, fit one logistic regression to each sample, and average the resulting predictions.

Bagged logistic regression predicts conversion probability; a further mathematical decomposition converts that prediction into touchpoint contribution.

The paper procedure quoted in the source note was:

1. For a dataset, sample a proportion `p_s` of observations and a proportion `p_c` of covariates. Fit logistic regression on the sampled observations and covariates and record the estimated coefficients.
2. Repeat for `M` iterations and take each covariate's final estimate as the mean of its `M` estimated coefficients.

The note emphasizes two sampling layers:

1. At the population level, repeat `S` times, splitting each sample into training and testing data.
2. Inside each training dataset, repeat `M` times, selecting a proportion of records and a proportion of covariates.

The motivation is collinearity among variables, which can make regression coefficients high-variance and unstable. Randomly selecting covariate subsets in bagging can reduce estimation variability, trading bias against variance. The note identifies that the result is not unbiased.

### Simple Probabilistic Model

**Step 1:** calculate empirical probabilities for each principal factor:

$$
P(y\mid x_i)=\frac{N_{+}(x_i)}{N_{+}(x_i)+N_{-}(x_i)}
$$

and pairwise conditional probabilities:

$$
P(y\mid x_i,x_j)=\frac{N_{+}(x_i,x_j)}{N_{+}(x_i,x_j)+N_{-}(x_i,x_j)}
$$

`y` is a binary conversion outcome such as purchase or sign-up, and `x_i`, for `i = 1,...,p`, denotes one of `p` advertising channels.

**Step 2:** compute the contribution of channel `i` for each positive user:

$$
C(x_i)=P(y\mid x_i)+\frac{1}{2N}\sum_j\left[P(y\mid x_i,x_j)-P(y\mid x_i)-P(y\mid x_j)\right]
$$

The note interprets the first term as `x_i`'s individual contribution. For simultaneous `x_i` and `x_j`, total value is decomposed into `x_i`, `x_j`, and their synergy; synergy is split between the channels and averaged across relevant users/interactions.

The recorded limitation is bias: both `P(y | x_i)` and `P(y | x_i,x_j)` contain contributions from other covariates. Differences cancel some but not all of that influence.

### Comparing the Two Models

The paper's qualitative comparison is:

- Bagged logistic regression is more accurate and flexible when there are many covariates but somewhat harder to interpret.
- The probabilistic model is less accurate but more intuitive.
- Comparing both can cross-validate the broad conclusions of an overall advertising-Campaign analysis.

## Project Application

The source note proposed using bagged logistic regression and the probabilistic model together and treating similar conclusions as additional confidence. This is a historical research proposal, not current implementation: the repository currently compares weighted Markov removal effects with path-level Shapley and governs reliability through calculation validity, raw support, and model consistency.
