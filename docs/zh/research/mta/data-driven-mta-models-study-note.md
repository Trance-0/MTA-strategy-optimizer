# 介绍

MTA:
Unlike predictive models, the stability of the estimation
is especially important here because attribution model
determines the performance metric for the ad campaign.

NOT A PREDICTIVE MODLE!!!
MTA is for interpreting!!

attribution model是一个大类
MTA是attribution model中model的一类

Attribution Model 归因模型
│
├── Single-touch Attribution 单触点归因
│   ├── First Touch Attribution
│   └── Last Touch Attribution
│
└── Multi-touch Attribution 多触点归因，MTA
    ├── Linear Attribution
    ├── Time Decay Attribution
    ├── Position-Based Attribution
    ├── Markov Chain Attribution
    ├── Shapley Value Attribution
    ├── Bagged Logistic Regression Attribution
    └── Probabilistic Attribution Model

advertising tactic is judged by the metric in the attribution model

FOR MTA
in this artical, there are two model:
bagged logistic regression and simple probabilistic model

## 前备知识

### v-metric and a-metric

无论是bagged logistic regression 还是usual logistic regression
都会在population中进行sampling 然后一部分作为traning data
一部分作为testing data
进行s次实验 然后得到每次得到实验的coefficient用在testing data进行实验
每一个s都对应着 抽样，训练，测试 然后计算v-metric and a-metric

#### a-metric

a-metric（accuracy） 衡量准不准确
也就是模型能不能把用户正确分成：
positive user：发生转化的用户
negative user：没有转化的用户
在这两个model里 A-metric 实际上用的是 misclassification error rate
公式可以理解成：
A = 1/S*(sum(error))
其中 S 是重复实验次数，Error 是第 s 次测试集上的分类错误率

#### v-metric

v-metric(variance) 衡量稳不稳定
比如
第一次训练，google 的贡献系数是 2.1；
第二次训练，google 变成 0.8；
第三次又变成 3.5。
但是我们有很多个channal 有google facebook etc. 共p个渠道 s次实验
V = 1/p*(sum(SD(xi)))

### logistic regression model

logistic regression model:一种常见的机器学习分类模型
通常用来预测一个结果是不是会发生
eg.
用户路径：Facebook ad → Google search → Email
模型输出：转化概率 = 0.72

普通线性回归是：
y = β0 + β1x1 + β2x2 + β3x3 + ...
它的输出可以是任何数，比如 -3、0.5、10。

但转化概率必须在 0 到 1 之间ß。
所以 logistic regression 会先算一个线性回归：
z = β0 + β1x1 + β2x2 + β3x3 + ...
然后把这个 z 放进 sigmoid 函数：
p = 1 / (1 + e^(-z))
这样输出的 p 一定在 0 到 1 之间。
比如：
p = 0.8
就表示转化概率是 80%。

算法过程：
step1:数据
从population中进行sampling training data和testing data
在traning data上进行训练

| 用户  | Facebook | Google | Email | 是否转化 |
| ---   | -------  | -----  | ----  | ---      |
| 用户1 |        1 |      1 |     0 |    1     |
| 用户2 |        0 |      1 |     1 |    1     |
| 用户3 |        1 |      0 |     0 |    0     |
| 用户4 |        0 |      0 |     1 |    0     |

这里facebook,google,email 是自变量，是否转化是因变量
step2:初始化系数
模型一开始不知道每个渠道的影响，所以先随机给每个变量一个系数。
eg.
β0 = 0
β1 = 0.1
β2 = 0.1
β3 = 0.1
Step3:计算预测概率
先算：z = β0 + β1x1 + β2x2 + β3x3
然后算：
p = 1 / (1 + e^(-z))
比如用户1:
| 用户  | Facebook | Google | Email | 是否转化 |
| 用户1 |        1 |      1 |     0 |      1 |
模型算出：p = 0.75
意思是预测这个用户有 75% 的概率转化
Step 4：计算预测错了多少
模型会比较：预测概率p和真实结果y
如果真实 y = 1，但模型预测 p = 0.2，说明模型预测得很差。
如果真实 y = 1，模型预测 p = 0.9，说明模型预测得比较好。
Logistic regression通常用log loss / cross-entropy loss 来衡量错误：
Loss = -[y log(p) + (1-y) log(1-p)]
Step 5：更新系数
模型会不断调整 β，让 Loss 变小。
常见方法是：gradient descent 梯度下降
意思是：找到让错误率下降最快的方向 然后一点点调整参数

最后输出的是概率

## two MTA model

### bagged logistic regression model

bagged：bagging 集成方法
Bagging 全称是 Bootstrap Aggregating
原始数据
   ↓
随机抽样出很多份训练数据
   ↓
每一份数据训练一个 logistic regression
   ↓
得到很多个 logistic regression 模型
   ↓
把它们的预测结果平均

bagged logistic regression 负责预测转化概率，在通过数学方式把这个预测结果进一步拆解成每个触点的贡献。

FOR bagged logistic regression

Step 1. For a given data set, sample a proportion ps of
all the sample observations and a proportion pc of all
the covariates. Fit a logistic regression model on the
sampled covariates and the sampled data. Record the
estimated coefficients.

Step 2. Repeat Step 1 for M iterations, and the final
coefficient estimate for each covariate is taken as the
average of estimated coefficients in M iterations.

！！！！！NOTE THAT！！！！
在这里我们既要抽取一部分数据（ps of all the sample observation）和一部分的变量（pc of all the covariates）
在bagged logistic regression中 其实有两层sampling
第一层 在全部数据population中进行一次sampling 共S次
一部分作为traning data
一部分作为testing data
在traning data中还要sampling 共M次
每次收取一定比例的sample 一定比例的covariate

原因：注意 由于我们数据的变量可能会存在共线性 这会导致regression的结果出现很大的variance 不稳定 所以我们通过只随机选取一部分covariate的方式进行bagged，这样可以消除 共线性带来的estimation variability
trade-off bias 和 variance

缺陷：不是unbias

### simple probabilistic model

Step 1.
For a given data set, compute the empirical probability of the main factors,
P(y|xi)= Npositive(xi)/ [Npositive(xi)+Nnegative(xi)]

the pair-wise conditional probabilities
P(y|xi, xj)=Npositive(xi,xj)/[Npositive(xi,xj)+Nnegative(xi,xj)]

Here y is a binary outcome variable denoting a conversion event (purchase or sign-up), and
xi, i = 1,....., p, denote p different advertising channels.

Step 2.
The contribution of channel i is then computed at each positive user level as:
C(xi)=p(y|xi)+(1/(2N))*sum{[p(y|xi,xj)-p(y|xi)-p(y|xj)]}

拆解为两部分 第一部分的为单独xi channal的contribution
剩下一部分可以这么理解：在同时用xi和xj的时候 我们把贡献拆分成三份 xj的贡献 xi的贡献 xj和xi的协同贡献 然后协同贡献除2 但是协同贡献具有特异性（和每个人的协同贡献不一样） 所以还要除以N—1

缺陷：无论是P(y|xi)还是P(y|xi, xj) 其实都掺杂了其他人的贡献值 所以有bias 但是对于差值 所有其他的covariate的贡献都抵消了 但是不完全

### 对比两个model

Having two different modeling approaches give advertiser the flexibility to choose. The bagged logistic regression model is more accurate and more flexible with a larger number of covariates. It is slightly more difficult to interpret.
On the other hand, the probabilistic model is less accurate
but much more intuitive to interpret. In addition, the result
from both models can cross-validate the general conclusion
reached in the overall advertising campaign analysis.

## 项目应用

在项目中不止使用一种MTA model 同时使用bagged logistic regression and probabilistic model 两者数据差不多 增加可信度
