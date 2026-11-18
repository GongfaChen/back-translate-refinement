# 真实案例：before / after

> 由 `run_real_case.py` 自动生成，请勿手工编辑。
> 源稿为作者本人中文论文稿（已脱敏：桥名→某中承式拱桥，作者与单位信息已移除）。
> 只列出正文段；`##` 标题与中文逐字对应的不重复呈现。

共 14 个块（含标题），**7 段被精修改动**。

## 逐段并列

### 段 1

**中文原稿**

> 针对运行荷载变化下桥面振动特征易受干扰、异常检出难以直接给出吊杆状态信息的问题，提出模态空间异常指数（Modal-Space Anomaly Index，MSAI）与卷积神经网络–岭回归融合模型构成的两阶段识别方法（MSAI–CNN/Ridge）。第一阶段以正常响应为参考，融合时域重构、频带、空间能量与正常子空间偏差识别异常；第二阶段结合波形与统计特征，估计索力下降比例或判别异常吊杆组合。数值分析中，MSAI 平均 AUC 为 0.9962，融合回归 MAE 为 0.0095；固定回归输出并引入 MSAI 筛查后，完整识别率由 93.70% 提高至 98.90%，识别错误减少 82.5%。缩尺第二阶段组合分类准确率为 99.00%，包含正常状态的四类联合识别准确率为 98.14%，宏平均 F1 为 0.9814。斜拉桥换索案例进一步采用独立的通道关系残差开展探索性筛查，并通过激励对照分析现场响应变化。两阶段方法将异常发现与程度、位置判别相衔接，为桥面振动监测提供可用于针对性检查的吊杆状态信息。

**英文 · 初稿**

> To address interference from varying operational loads and the limited hanger-state information provided by anomaly detection alone, a two-stage method combines a Modal-Space Anomaly Index (MSAI) with convolutional neural network–ridge regression models (MSAI–CNN/Ridge). The first stage uses normal responses as a reference and integrates time-domain reconstruction, frequency-band, spatial-energy, and normal-subspace deviations to detect anomalies. The second stage combines waveform and statistical features to estimate tension reduction or classify predefined anomalous hanger combinations. In the numerical study, MSAI achieves a mean AUC of 0.9962, and the fused regression achieves an MAE of 0.0095. With identical regression predictions, introducing MSAI screening increases complete identification accuracy from 93.70% to 98.90% and reduces identification errors by 82.5%. In the scaled-model tests, second-stage combination classification achieves 99.00% accuracy, while joint identification of four states, including the normal state, achieves 98.14% accuracy and a macro-F1 of 0.9814. A supplementary cable-stayed bridge cable-replacement case uses an independent inter-channel residual model for exploratory screening and excitation controls to examine field response changes. The method connects anomaly detection with tension-reduction estimation and combination classification, providing hanger-state information for targeted inspections based on deck vibrations.

**英文 · 精修**

> To address the susceptibility of deck-vibration features to interference under varying operational loads and the difficulty for anomaly detection alone to provide hanger-state information directly, a two-stage identification method is proposed that combines a Modal-Space Anomaly Index (MSAI) with a convolutional neural network–ridge regression model (MSAI–CNN/Ridge). The first stage uses normal responses as a reference and integrates time-domain reconstruction, frequency-band, spatial-energy, and normal-subspace deviations to detect anomalies. The second stage combines waveform and statistical features to estimate the tension reduction ratio or discriminate anomalous hanger combinations. In the numerical study, MSAI achieves a mean AUC of 0.9962, and the fused regression achieves an MAE of 0.0095. With identical regression predictions, introducing MSAI screening increases complete identification accuracy from 93.70% to 98.90% and reduces identification errors by 82.5%. In the scaled-model tests, second-stage combination classification achieves 99.00% accuracy, while joint identification of four states, including the normal state, achieves 98.14% accuracy and a macro-F1 of 0.9814. A supplementary cable-stayed bridge cable-replacement case uses an independent inter-channel residual model for exploratory screening and excitation controls to examine field response changes. The two-stage method links anomaly detection with the discrimination of degree and location, providing hanger-state information that can be used for targeted inspection in deck-vibration monitoring.

编辑点：

- `语义改写`：`interference from` → `the susceptibility of deck-vibration features to interference under`
- `语义改写`：`limited hanger-state information provided by anomaly detection alone , a two-stage method` → `difficulty for anomaly detection alone to provide hanger-state information directly , a two-stage identification method is proposed that`
- `语义改写`：`` → `a`
- `语义改写`：`tension reduction or classify predefined` → `the tension reduction ratio or discriminate`
- `语义改写`：`method connects anomaly detection with tension-reduction estimation and combination classification` → `two-stage method links anomaly detection with the discrimination of degree and location`
- `语义改写`：`for targeted inspections based on deck vibrations .` → `that can be used for targeted inspection in deck-vibration monitoring .`
- `术语/搭配归一`：`models` → `model`

### 段 2

**中文原稿**

> 当异常标签有限时，无监督学习可以仅依靠正常数据建立参考状态。单类分类、自编码器和车辆通过响应已经用于桥梁异常检测 [9–11] 。Teng 等将重构误差与结构相似性结合 [12] ，并进一步引入自注意力机制识别渐进式损伤 [13] 。异常监测数据的分类与定位研究推动了数据质量识别 [14–15] ，深度学习也被用于结构损伤检测与定位 [16] 。为降低桥梁、环境和测点差异的影响，研究者引入域自适应与迁移学习 [17–19] ，并研究统计对齐方法 [20] ；卷积、注意力与循环网络的组合 [21] 及基于时频特征的分类方法 [22] 则提供了不同的响应表征方式。这些研究为振动状态识别奠定了基础，但异常筛查与索力变化程度、异常吊杆位置的确定仍需在统一流程中评价。

**英文 · 初稿**

> When anomaly labels are limited, unsupervised learning can establish a reference state using only normal data. One-class classification, autoencoders and vehicle-passage responses have already been used for bridge anomaly detection [9–11]. Teng et al. combined reconstruction error with structural similarity [12], and further introduced a self-attention mechanism to identify progressive damage [13]. Research on the classification and localization of anomalous monitoring data has advanced data-quality identification [14–15], and deep learning has also been applied to structural damage detection and localization [16]. To reduce the influence of differences among bridges, environments and measurement points, researchers have introduced domain adaptation and transfer learning [17–19], and studied statistical alignment methods [20]; combinations of convolutional, attention and recurrent networks [21] and classification methods based on time–frequency features [22] provide alternative ways of representing responses. These studies have laid the foundation for vibration state identification, but anomaly screening together with the determination of the degree of tension change and the location of anomalous hangers still needs to be evaluated within a unified procedure.

**英文 · 精修**

> When anomaly labels are limited, unsupervised learning can establish a reference state using only normal data. One-class classification, autoencoders and vehicle-passage responses have already been used for bridge anomaly detection [9–11]. Teng et al. combined reconstruction error with structural similarity [12], and further introduced a self-attention mechanism to identify progressive damage [13]. Research on the classification and localisation of anomalous monitoring data has advanced data-quality identification [14–15], and deep learning has also been applied to structural damage detection and localisation [16]. To reduce the influence of differences among bridges, environments and measurement points, researchers have introduced domain adaptation and transfer learning [17–19], and studied statistical alignment methods [20]; combinations of convolutional, attention and recurrent networks [21] and classification methods based on time–frequency features [22] provide alternative ways of representing responses. These studies have laid the foundation for vibration state identification, but anomaly screening together with the determination of the degree of tension change and the location of anomalous hangers still needs to be evaluated within a unified procedure.

编辑点：

- `拼写体系归一(en-US→en-GB)`：`localization` → `localisation`
- `拼写体系归一(en-US→en-GB)`：`localization` → `localisation`

### 段 3

**中文原稿**

> 数值研究采用外形长 16.30 m、宽 3.94 m、高 2.99 m 的中承式系杆拱桥梁–壳混合单元模型（图 1），外形尺寸与某中承式拱桥缩尺试验模型一致 [34–35] 。钢材弹性模量为 209 GPa，泊松比为 0.30，密度为 7,800 kg/m³；壳厚 3 mm，数值吊杆梁截面半径 13 mm，共 49 根吊杆。三个支承节点集合均约束六个自由度，横梁与桥面采用 42 组刚性梁式多点约束连接。各索力状态共用支承、截面与质量参数，以比较吊杆轴力变化的影响。重力加速度取 9.80 m/s²，动力分析采用前 10 阶质量归一化模态，模态阻尼比取 0.05。主要参数见表 1。

**英文 · 初稿**

> The numerical study uses a half-through tied-arch beam–shell mixed-element model with an overall length of 16.30 m, a width of 3.94 m and a height of 2.99 m (Fig. 1), and its overall dimensions are consistent with those of the scaled test model of the target arch bridge[34–35]. The steel has an elastic modulus of 209 GPa, a Poisson's ratio of 0.30 and a density of 7,800 kg/m³; the shell thickness is 3 mm, and the numerical hangers are beam sections with a radius of 13 mm, 49 hangers in total. All six degrees of freedom are constrained at each of the three support node sets, and the cross beams and the deck are connected by 42 sets of rigid beam-type multi-point constraints. All tension states share the same support, section and mass parameters so that the effect of the hanger axial force variation can be compared. The gravitational acceleration is taken as 9.80 m/s², the dynamic analysis uses the first 10 mass-normalized modes, and the modal damping ratio is 0.05. The main parameters are listed in Table 1.

**英文 · 精修**

> The numerical study uses a half-through tied-arch beam–shell mixed-element model with an overall length of 16.30 m, a width of 3.94 m and a height of 2.99 m (Fig. 1), and its overall dimensions are consistent with those of the scaled test model of the target arch bridge[34–35]. The steel has an elastic modulus of 209 GPa, a Poisson's ratio of 0.30 and a density of 7,800 kg/m³; the shell thickness is 3 mm, and the numerical hangers are beam sections with a radius of 13 mm, 49 hangers in total. All six degrees of freedom are constrained at each of the three support node sets, and the cross beams and the deck are connected by 42 sets of rigid beam-type multi-point constraints. All tension states share the same support, section and mass parameters so that the effect of the hanger axial force variation can be compared. The gravitational acceleration is taken as 9.80 m/s², the dynamic analysis uses the first 10 mass-normalised modes, and the modal damping ratio is 0.05. The main parameters are listed in Table 1.

编辑点：

- `语义改写`：`mass-normalized` → `mass-normalised`

### 段 4

**中文原稿**

> 第一阶段 CAE、输入标准化及正常子空间由正常训练集拟合；误差分量的参考统计量、融合得分尺度和报警阈值由正常验证集确定。第二阶段及直接监督对照使用各自训练集拟合参数，按照第 3.2 节的验证规则选择配置，测试期间均保持固定。

**英文 · 初稿**

> In the first stage, the CAE, the input standardization and the normal subspace are fitted from the normal training set; the reference statistics of the error components, the fused-score scale and the alarm threshold are determined from the normal validation set. The second stage and the direct supervised controls use parameters fitted on their respective training sets, their configurations are selected according to the validation rules in Section 3.2, and all remain fixed during testing.

**英文 · 精修**

> In the first stage, the CAE, the input standardisation and the normal subspace are fitted from the normal training set; the reference statistics of the error components, the fused-score scale and the alarm threshold are determined from the normal validation set. The second stage and the direct supervised controls use parameters fitted on their respective training sets, their configurations are selected according to the validation rules in Section 3.2, and all remain fixed during testing.

编辑点：

- `拼写体系归一(en-US→en-GB)`：`standardization` → `standardisation`

### 段 5

**中文原稿**

> 训练损失同时约束时域与频带重构，并用输入频带均方能量归一化频带误差，见式（3）。带通 FIR 滤波器采用 31 个抽头（30 阶），由 2 至 6 Hz 理想带通 sinc 核乘 Hamming 窗得到，再按系数绝对值之和归一化。卷积两端各补 15 个零并保持原长度，全部输出参与损失计算；频带权重取 0.35。

**英文 · 初稿**

> The training loss constrains both the time-domain and the frequency-band reconstruction and normalizes the frequency-band error by the mean-square energy of the input band, as given in Eq. (3). The band-pass FIR filter uses 31 taps (order 30), is obtained by multiplying a 2–6 Hz ideal band-pass sinc kernel by a Hamming window, and is then normalized by the sum of the absolute values of the coefficients. Fifteen zeros are padded at each end of the convolution while the original length is maintained, and all outputs participate in the loss computation; the band weight is taken as 0.35.

**英文 · 精修**

> The training loss constrains both the time-domain and the frequency-band reconstruction and normalises the frequency-band error by the mean-square energy of the input band, as given in Eq. (3). The band-pass FIR filter uses 31 taps (order 30), is obtained by multiplying a 2–6 Hz ideal band-pass sinc kernel by a Hamming window, and is then normalised by the sum of the absolute values of the coefficients. At each end of the convolution, 15 zeros are padded while the original length is maintained, and all outputs participate in the loss computation; the band weight is taken as 0.35.

编辑点：

- `语义改写`：`Fifteen zeros are padded at` → `At`
- `语义改写`：`` → `, 15 zeros are padded`
- `拼写体系归一(en-US→en-GB)`：`normalizes` → `normalises`
- `拼写体系归一(en-US→en-GB)`：`normalized` → `normalised`

### 段 6

**中文原稿**

> 输入时长比较采用同源配对取样。4.0 s 片段的起点依次为 0、0.5、1.0、1.5 和 2.0 s；对应 0.5 s 片段取长片段的中央部分，起点依次为 1.75、2.25、2.75、3.25 和 3.75 s。两种输入共享状态标签和车辆工况分组，分别完成去均值、共同 RMS 归一化与标准化。每对样本均归入同一训练、验证或测试集合。

**英文 · 初稿**

> The input-duration comparison uses paired sampling from the same source. The starting points of the 4.0 s segments are 0, 0.5, 1.0, 1.5 and 2.0 s in turn; the corresponding 0.5 s segments take the central part of the long segment, with starting points of 1.75, 2.25, 2.75, 3.25 and 3.75 s in turn. The two input types share the same state labels and vehicle-case grouping, and each completes mean removal, common-RMS normalization and standardization separately. Each pair of samples is assigned to the same training, validation or test set.

**英文 · 精修**

> The input-duration comparison uses paired sampling from the same source. The starting points of the 4.0 s segments are 0, 0.5, 1.0, 1.5 and 2.0 s in turn; the corresponding 0.5 s segments take the central part of the long segment, with starting points of 1.75, 2.25, 2.75, 3.25 and 3.75 s in turn. The two input types share the same state labels and vehicle-case grouping, and each completes mean removal, common-RMS normalisation and standardisation separately. Each pair of samples is assigned to the same training, validation or test set.

编辑点：

- `拼写体系归一(en-US→en-GB)`：`normalization and standardization` → `normalisation and standardisation`

### 段 7

**中文原稿**

> 实桥案例选取斜拉桥 C4 拉索移除与更换后两种状态，C3、C5 和 C6 通道的传感器固定在相应桥面位置。在 C1 结构状态保持不变的条件下，设置无敲击、平面内敲击和平面外敲击三种激励，分析激励变化对筛查结果的影响。桥梁概貌、换索现场与测点相对布置见图 5。

**英文 · 初稿**

> The full-scale bridge case takes the two states of stay cable C4 of a cable-stayed bridge before removal and after replacement, with the sensors of channels C3, C5 and C6 fixed at the corresponding deck positions. With the structural state at C1 unchanged, three excitations are set - no tapping, in-plane tapping and out-of-plane tapping - to analyse the influence of excitation changes on the screening results. The general view of the bridge, the cable-replacement site and the relative arrangement of the measurement points are shown in Fig. 5.

**英文 · 精修**

> The full-scale bridge case takes the two states of stay cable C4 of a cable-stayed bridge before removal and after replacement, with the sensors of channels C3, C5 and C6 fixed at the corresponding deck positions. With the structural state at C1 unchanged, three excitations are set: no tapping, in-plane tapping and out-of-plane tapping, to analyse the influence of excitation changes on the screening results. The general view of the bridge, the cable-replacement site and the relative arrangement of the measurement points are shown in Fig. 5.

编辑点：

- `标点与结构`：`-` → `:`
- `标点与结构`：`-` → `,`

## 统计

| 类别 | 编辑点数 |
|---|---|
| 拼写体系归一(en-US→en-GB) | 6 |
| 数字形式统一 | 0 |
| 术语/搭配归一 | 1 |
| 标点与结构 | 2 |
| 语义改写 | 9 |
| **合计** | 18 |

分类口径：

- **拼写体系归一**：normalization→normalisation 这类 en-US→en-GB，占绝大多数的机械替换；
- **术语/搭配归一**：去掉多余连字符（regression-output→regression output）、单复数、同义改称（classify→discriminate）；
- **标点与结构**：破折号夹注改冒号、句式连接调整；
- **语义改写**：以上都不属于、确实改了措辞或补了信息的编辑点。

受保护元素（数字、引用、Eq. 编号）在初稿→精修之间**零变动**，由脚本逐块校验。
