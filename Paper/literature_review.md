# Literature Review: Differentiable Robust Optimization for Learning Correlated Uncertainty Sets in Operating Reserve Markets

This document provides a comprehensive literature review organized by research thread, with details on each paper's contribution and its relation to our work.

---

## A) Robust Optimization Foundations

### 1. Ben-Tal & Nemirovski (1998)
**Citation:** A. Ben-Tal and A. Nemirovski, "Robust convex optimization," *Mathematics of Operations Research*, vol. 23, no. 4, pp. 769–805, 1998.

**Summary:** Foundational paper establishing the theory of robust convex optimization. Develops tractable robust counterparts for uncertain convex programs by reformulating worst-case constraints as deterministic convex constraints using support functions and duality.

**Relation:** Our gauge-based uncertainty set formulation (Definition 1) and support function reformulation (Eq. 2) build directly on this framework. The robust counterpart approach is the basis for converting uncertain constraints into deterministic ones via support functions.

**Gap filled:** Ben-Tal & Nemirovski treat the uncertainty set as fixed; our work learns the uncertainty set geometry end-to-end from data.

---

### 2. Ben-Tal, El Ghaoui, & Nemirovski (2009)
**Citation:** A. Ben-Tal, L. El Ghaoui, and A. Nemirovski, *Robust Optimization*. Princeton, NJ: Princeton University Press, 2009.

**Summary:** Comprehensive textbook covering the theory, methodology, and applications of robust optimization. Presents ellipsoidal, polyhedral, and general convex uncertainty sets with tractable reformulations for linear, conic, and semidefinite programs.

**Relation:** Provides the theoretical underpinning for our gauge-based uncertainty set framework, including support function calculus and duality-based reformulations used throughout Sections II and III.

**Gap filled:** The textbook prescribes fixed uncertainty set geometries; our framework parameterizes and optimizes the geometry.

---

### 3. Bertsimas & Sim (2004)
**Citation:** D. Bertsimas and M. Sim, "The price of robustness," *Operations Research*, vol. 52, no. 1, pp. 35–53, 2004.

**Summary:** Introduces budget-of-uncertainty sets (polyhedral) that provide a tractable way to control the degree of conservatism in robust linear optimization. Demonstrates that the price of robustness (additional cost for protection) can be quantified.

**Relation:** Our work addresses the same fundamental trade-off between robustness and cost, but through a learned ellipsoidal geometry rather than a fixed budget parameter. The profiled objective J_P(θ) explicitly optimizes this trade-off.

**Gap filled:** Budget-of-uncertainty sets have fixed rectangular geometry; our ellipsoidal sets capture correlations and are optimized for decision cost.

---

### 4. Bertsimas, Brown, & Caramanis (2011)
**Citation:** D. Bertsimas, D. B. Brown, and C. Caramanis, "Theory and applications of robust optimization," *SIAM Review*, vol. 53, no. 3, pp. 464–501, 2011.

**Summary:** Comprehensive survey of robust optimization theory and applications, covering static and adaptive formulations, computational tractability, and connections to risk measures and stochastic programming.

**Relation:** Provides context for our work within the broader RO landscape. Our envelope gradient approach (Theorem 1) and the two structural regimes extend the methodology presented here.

**Gap filled:** Survey covers traditional RO with fixed sets; our contribution is differentiable, data-driven RO with learned sets.

---

### 5. Gorissen, Yanikoğlu, & den Hertog (2015)
**Citation:** B. L. Gorissen, İ. Yanikoğlu, and D. den Hertog, "A practical guide to robust optimization," *Omega*, vol. 53, pp. 124–137, 2015.

**Summary:** Provides practical guidance for implementing robust optimization, including how to choose uncertainty set shapes and sizes, handle adjustable decisions, and manage computational complexity.

**Relation:** Our work addresses the fundamental question raised here: how to choose uncertainty set geometry. Rather than manual selection, we automate it through end-to-end learning.

**Gap filled:** Practical guidelines for manual uncertainty set selection; our framework automates this selection via gradient-based optimization.

---

## B) Robust Optimization for Unit Commitment and SCED

### 6. Bertsimas, Litvinov, Sun, Zhao, & Zheng (2013)
**Citation:** D. Bertsimas, E. Litvinov, X. A. Sun, J. Zhao, and T. Zheng, "Adaptive robust optimization for the security constrained unit commitment problem," *IEEE Trans. Power Syst.*, vol. 28, no. 1, pp. 52–63, Feb. 2013.

**Summary:** Develops an adaptive (two-stage) robust optimization approach for security-constrained unit commitment with polyhedral uncertainty sets representing wind generation variability. Uses Benders decomposition for computational tractability.

**Relation:** Our SCED formulation (Section IV) is a descendant of this work's framework. The key difference is that we learn the uncertainty set shape rather than prescribing polyhedral geometry a priori.

**Gap filled:** Uses fixed polyhedral uncertainty sets; our ellipsoidal sets capture spatial correlations and are learned from data.

---

### 7. Jiang, Wang, & Guan (2012)
**Citation:** R. Jiang, J. Wang, and Y. Guan, "Robust unit commitment with wind power and pumped storage hydro," *IEEE Trans. Power Syst.*, vol. 27, no. 2, pp. 800–810, May 2012.

**Summary:** Proposes a two-stage robust unit commitment model that accounts for wind power uncertainty using polyhedral uncertainty sets. Develops a column-and-constraint generation algorithm for solution.

**Relation:** Demonstrates the importance of uncertainty set design in power system scheduling. Our work extends this line by enabling data-driven, correlation-aware uncertainty sets.

**Gap filled:** Fixed polyhedral uncertainty sets with manually specified bounds; our approach learns correlation structure automatically.

---

### 8. Zeng & Zhao (2013)
**Citation:** B. Zeng and L. Zhao, "Solving two-stage robust optimization problems using a column-and-constraint generation method," *Operations Research Letters*, vol. 41, no. 5, pp. 457–461, 2013.

**Summary:** Proposes the column-and-constraint generation (C&CG) algorithm for solving two-stage robust optimization problems, which is more efficient than Benders decomposition for many problems.

**Relation:** The C&CG algorithm is a standard solver for the inner robust optimization problems in our framework. Our envelope gradient approach complements such solvers by extracting gradient information from dual solutions.

**Gap filled:** Focuses on solving RO problems; our work focuses on learning the uncertainty set parameters that define the problem.

---

### 9. Lorca, Sun, Litvinov, & Zheng (2016)
**Citation:** Á. Lorca, X. A. Sun, E. Litvinov, and T. Zheng, "Multistage adaptive robust optimization for the unit commitment problem," *Operations Research*, vol. 64, no. 1, pp. 32–51, 2016.

**Summary:** Extends adaptive robust optimization to multistage settings for unit commitment, using piecewise linear decision rules and polyhedral uncertainty sets to capture temporal evolution of uncertainty.

**Relation:** Addresses temporal aspects of uncertainty that complement our spatial correlation modeling. Our framework could extend to multistage settings using the same gauge-based uncertainty set approach.

**Gap filled:** Fixed multistage polyhedral uncertainty; our approach enables learned, context-dependent uncertainty geometry.

---

### 10. Jabr (2013)
**Citation:** R. A. Jabr, "Adjustable robust OPF with renewable energy sources," *IEEE Trans. Power Syst.*, vol. 28, no. 4, pp. 4742–4751, 2013.

**Summary:** Develops adjustable robust optimal power flow (OPF) incorporating renewable energy uncertainty with affine recourse policies. Uses polyhedral and ellipsoidal uncertainty sets.

**Relation:** One of the early power systems papers using ellipsoidal uncertainty sets, which is the same geometric family we use. Our work adds the ability to learn the ellipsoid shape from data.

**Gap filled:** Uses fixed ellipsoidal sets with prescribed covariance; our framework learns the Cholesky factor from data.

---

## C) Distributionally Robust Optimization

### 11. Mohajerin Esfahani & Kuhn (2018)
**Citation:** P. Mohajerin Esfahani and D. Kuhn, "Data-driven distributionally robust optimization using the Wasserstein metric: performance guarantees and tractable reformulations," *Mathematical Programming*, vol. 171, no. 1–2, pp. 115–166, 2018.

**Summary:** Develops Wasserstein-distance-based distributionally robust optimization with finite-sample performance guarantees. Shows tractable reformulations for a broad class of loss functions.

**Relation:** Provides an alternative paradigm (DRO) to our robust optimization approach for handling distributional uncertainty. While DRO optimizes over distributions, our approach directly optimizes the geometric uncertainty set for downstream cost.

**Gap filled:** DRO uses distributional ambiguity sets (balls in probability space); our approach works with geometric uncertainty sets in decision space, enabling direct gradient computation via support functions.

---

### 12. Xiong, Jirutitijaroen, & Singh (2017)
**Citation:** P. Xiong, P. Jirutitijaroen, and C. Singh, "A distributionally robust optimization model for unit commitment considering uncertain wind power generation," *IEEE Trans. Power Syst.*, vol. 32, no. 1, pp. 39–49, 2017.

**Summary:** Applies DRO with moment-based ambiguity sets to unit commitment under wind uncertainty. Constructs ambiguity sets using first- and second-order moment constraints.

**Relation:** Uses moment-based DRO for the same application domain (power systems under renewable uncertainty). Our approach differs by learning geometric uncertainty sets and using conformal calibration rather than moment constraints.

**Gap filled:** Moment-based ambiguity sets are fixed; our approach learns flexible ellipsoidal geometry optimized for dispatch cost.

---

### 13. Zhao & Guan (2016)
**Citation:** C. Zhao and Y. Guan, "Data-driven stochastic unit commitment for integrating wind generation," *IEEE Trans. Power Syst.*, vol. 31, no. 4, pp. 2587–2596, 2016.

**Summary:** Proposes data-driven stochastic unit commitment that constructs uncertainty sets from historical wind data. Uses confidence-set-based approaches calibrated from data.

**Relation:** Shares the data-driven philosophy of our work but constructs uncertainty sets via statistical estimation rather than end-to-end optimization for decision cost.

**Gap filled:** Data-driven set construction optimizes statistical fit; our approach optimizes for downstream decision quality.

---

### 14. Delage & Ye (2010)
**Citation:** E. Delage and Y. Ye, "Distributionally robust optimization under moment uncertainty with application to data-driven problems," *Operations Research*, vol. 58, no. 3, pp. 595–612, 2010.

**Summary:** Develops DRO with ambiguity sets defined by moment constraints (mean and covariance bounds) estimated from data. Shows tractable SDP reformulations.

**Relation:** The moment-based ambiguity sets parameterized by covariance bounds are related to our ellipsoidal uncertainty sets parameterized by Cholesky factors. Our approach optimizes the ellipsoid shape for decision cost rather than statistical fidelity.

**Gap filled:** Moment-based ambiguity sets from statistical estimation; our sets are learned end-to-end.

---

### 15. Gao & Kleywegt (2023)
**Citation:** R. Gao and A. J. Kleywegt, "Distributionally robust stochastic optimization with Wasserstein distance," *Mathematics of Operations Research*, vol. 48, no. 2, pp. 603–655, 2023.

**Summary:** Provides a comprehensive treatment of Wasserstein DRO, including sharp finite-sample guarantees, tractable reformulations, and connections to regularization.

**Relation:** Establishes theoretical foundations for DRO that parallel our conformal calibration approach for providing finite-sample guarantees. Both aim for distribution-free reliability.

**Gap filled:** Wasserstein DRO guarantees are distributional; our conformal guarantees are for geometric sets with finite-sample coverage under exchangeability.

---

## D) Chance-Constrained Optimization for Power Systems

### 16. Roald & Andersson (2018)
**Citation:** L. A. Roald and G. Andersson, "Chance-constrained AC optimal power flow: reformulations and efficient algorithms," *IEEE Trans. Power Syst.*, vol. 33, no. 3, pp. 2906–2918, 2018.

**Summary:** Develops reformulations and algorithms for chance-constrained AC optimal power flow, handling probabilistic constraints on voltage and thermal limits under Gaussian uncertainty.

**Relation:** Addresses similar power system constraints (thermal limits, voltage) under uncertainty but uses probabilistic (chance) constraints rather than robust constraints. Our work uses robust constraints with learned uncertainty sets.

**Gap filled:** Assumes Gaussian uncertainty for analytical reformulation; our approach is distribution-free via conformal calibration.

---

### 17. Bienstock, Chertkov, & Harnett (2014)
**Citation:** D. Bienstock, M. Chertkov, and S. Harnett, "Chance-constrained optimal power flow: risk-aware network control under uncertainty," *SIAM Review*, vol. 56, no. 3, pp. 461–495, 2014.

**Summary:** Comprehensive treatment of chance-constrained OPF, analyzing computational complexity and developing approximation algorithms for handling probabilistic constraints in power networks.

**Relation:** Addresses the same fundamental problem (network-constrained dispatch under uncertainty) but with probabilistic rather than robust formulation. Our envelope gradient approach provides an alternative computational strategy.

**Gap filled:** Chance-constrained formulations require distributional assumptions; our robust formulation with conformal calibration provides distribution-free guarantees.

---

## E) Operating Reserves and Renewable Integration

### 18. Papavasiliou, Oren, & O'Neill (2011)
**Citation:** A. Papavasiliou, S. S. Oren, and R. P. O'Neill, "Reserve requirements for wind power integration: a scenario-based stochastic programming framework," *IEEE Trans. Power Syst.*, vol. 26, no. 4, pp. 2197–2206, 2011.

**Summary:** Develops a stochastic programming framework for determining operating reserve requirements that account for wind power forecast uncertainty. Uses scenario-based approaches for reserve sizing.

**Relation:** Directly relevant to our application domain (operating reserves under renewable uncertainty). Our framework provides an alternative approach to reserve sizing that learns correlation structure rather than using scenario-based methods.

**Gap filled:** Scenario-based reserve sizing; our approach learns uncertainty set geometry that directly determines reserve requirements.

---

### 19. Morales, Conejo, Madsen, Pinson, & Zugno (2014)
**Citation:** J. M. Morales, A. J. Conejo, H. Madsen, P. Pinson, and M. Zugno, *Integrating Renewables in Electricity Markets: Operational Problems*. New York: Springer, 2014.

**Summary:** Comprehensive textbook on integrating renewable energy into electricity market operations, covering forecasting, stochastic programming, robust optimization, and market design.

**Relation:** Provides the application context for our work. Our framework addresses the operational challenges of renewable integration discussed here, specifically reserve procurement under correlated forecast errors.

---

### 20. Roald, Pozo, Papavasiliou, Molzahn, Kazempour, & Conejo (2023)
**Citation:** L. Roald, D. Pozo, A. Papavasiliou, D. Molzahn, J. Kazempour, and A. Conejo, "Power systems optimization under uncertainty: a review of methods and applications," *Electric Power Systems Research*, vol. 214, art. 108725, 2023.

**Summary:** Comprehensive review of optimization methods for power systems under uncertainty, covering stochastic programming, robust optimization, chance-constrained programming, and data-driven approaches.

**Relation:** Provides a recent survey that positions our work within the broader landscape. Our contribution addresses the gap they identify in integrating machine learning with robust optimization for uncertainty set design.

---

### 21. Hodge & Milligan (2011)
**Citation:** B.-M. Hodge and M. Milligan, "Wind power forecasting error distributions over multiple timescales," in *Proc. IEEE Power Energy Soc. General Meeting*, Detroit, MI, USA, 2011, pp. 1–8.

**Summary:** Empirically characterizes wind power forecast error distributions across multiple timescales (hour-ahead to day-ahead), documenting non-Gaussian, heavy-tailed, and time-varying behavior.

**Relation:** Motivates our approach: since forecast errors are non-Gaussian and have complex structure, learning the uncertainty set geometry from data is more appropriate than assuming fixed parametric forms.

---

### 22. Pinson (2013)
**Citation:** P. Pinson, "Wind energy: Forecasting challenges for its operational management," *Statistical Science*, vol. 28, no. 4, pp. 564–585, 2013.

**Summary:** Reviews statistical challenges in wind energy forecasting, including spatial and temporal correlations, non-stationarity, and the importance of probabilistic forecasts for operational management.

**Relation:** Directly motivates the need for correlation-aware uncertainty sets. The spatial correlations documented here are precisely what our learned Cholesky factors capture.

---

### 23. Hong & Fan (2016)
**Citation:** T. Hong and S. Fan, "Probabilistic electric load forecasting: a tutorial review," *International Journal of Forecasting*, vol. 32, no. 3, pp. 914–938, 2016.

**Summary:** Tutorial review of probabilistic load forecasting methods, covering parametric and nonparametric approaches, evaluation metrics, and practical considerations.

**Relation:** Provides context for the uncertainty quantification component of our work. Our conformal calibration approach provides distribution-free alternatives to the parametric methods reviewed here.

---

## F) Data-Driven Uncertainty Set Construction

### 24. Bertsimas, Gupta, & Kallus (2018)
**Citation:** D. Bertsimas, V. Gupta, and N. Kallus, "Data-driven robust optimization," *Mathematical Programming*, vol. 167, no. 2, pp. 235–292, 2018.

**Summary:** Develops a framework for constructing uncertainty sets from data using hypothesis testing, providing finite-sample guarantees on constraint satisfaction. Connects set size to sample complexity.

**Relation:** Shares the data-driven philosophy but constructs sets statistically rather than optimizing for decision cost. Their sets are calibrated for distributional coverage; ours are optimized for dispatch cost while maintaining conformal coverage.

**Gap filled:** Data-driven sets optimize statistical fit; our sets optimize economic cost while maintaining coverage via conformal calibration.

---

### 25. Ben-Tal, Goryashko, Guslitzer, & Nemirovski (2004)
**Citation:** A. Ben-Tal, A. Goryashko, E. Guslitzer, and A. Nemirovski, "Adjustable robust solutions of uncertain linear programs," *Mathematical Programming*, vol. 99, no. 2, pp. 351–376, 2004.

**Summary:** Introduces adjustable (two-stage) robust optimization with affine recourse policies. Shows that affine policies provide tractable approximations to fully adjustable solutions.

**Relation:** The adjustable RO framework is relevant to our zonal reserve formulation where reserve allocations serve as recourse decisions. Our framework extends this by learning the uncertainty set shape.

---

### 26. Van Parys, Mohajerin Esfahani, & Kuhn (2021)
**Citation:** B. P. G. Van Parys, P. Mohajerin Esfahani, and D. Kuhn, "From data to decisions: distributionally robust optimization is optimal," *Management Science*, vol. 67, no. 6, pp. 3387–3402, 2021.

**Summary:** Shows that distributionally robust optimization with Wasserstein ambiguity sets is asymptotically optimal among all data-driven decision rules, establishing a fundamental connection between DRO and data-driven decision-making.

**Relation:** Establishes optimality of DRO as a data-driven approach; our work provides an alternative optimality criterion (minimizing robust dispatch cost subject to conformal coverage).

---

## G) Decision-Focused Learning and Differentiable Optimization

### 27. Elmachtoub & Grigas (2022)
**Citation:** A. N. Elmachtoub and P. Grigas, "Smart 'predict, then optimize'," *Management Science*, vol. 68, no. 1, pp. 9–26, 2022.

**Summary:** Introduces the SPO+ loss for decision-focused learning, which directly optimizes predictions for downstream optimization quality rather than prediction accuracy. Shows convexity and Fisher consistency of the surrogate loss.

**Relation:** Our profiled objective J_P(θ) shares the decision-focused philosophy: we optimize uncertainty set shape for dispatch cost rather than statistical fit. However, our approach is for robust optimization rather than point prediction.

**Gap filled:** SPO+ addresses point predictions for deterministic optimization; our framework addresses uncertainty set learning for robust optimization.

---

### 28. Donti, Amos, & Kolter (2017)
**Citation:** P. L. Donti, B. Amos, and J. Z. Kolter, "Task-based end-to-end model learning in stochastic optimization," in *Proc. Adv. Neural Inf. Process. Syst.*, vol. 30, pp. 5484–5494, 2017.

**Summary:** Proposes end-to-end learning of predictive models by backpropagating through stochastic optimization problems, differentiating through the KKT conditions of the downstream optimization.

**Relation:** Our work shares the end-to-end learning philosophy but avoids differentiating through the optimization solver. Instead, we use envelope gradients from dual multipliers (Theorem 1), which is computationally cheaper and more numerically stable.

**Gap filled:** KKT-based differentiation requires solving linear systems at each gradient step; our envelope approach uses only dual multipliers from the forward solve.

---

### 29. Amos & Kolter (2017)
**Citation:** B. Amos and J. Z. Kolter, "OptNet: Differentiable optimization as a layer in neural networks," in *Proc. Int. Conf. Mach. Learn.*, pp. 136–145, 2017.

**Summary:** Introduces OptNet, which embeds quadratic programs as differentiable layers in neural networks by differentiating through the KKT conditions. Enables end-to-end learning through optimization.

**Relation:** OptNet differentiates through the QP solver; our approach explicitly avoids this via envelope gradients. This is a fundamental methodological distinction: we extract gradient information from dual multipliers without computing Jacobians of the solution map.

**Gap filled:** KKT differentiation; our envelope approach is solver-free for gradient computation.

---

### 30. Agrawal, Amos, Barratt, Boyd, Diamond, & Kolter (2019)
**Citation:** A. Agrawal, B. Amos, S. Barratt, S. Boyd, S. Diamond, and J. Z. Kolter, "Differentiable convex optimization layers," in *Proc. Adv. Neural Inf. Process. Syst.*, vol. 32, pp. 9558–9570, 2019.

**Summary:** Extends differentiable optimization layers to general disciplined convex programs using conic form and adjoint differentiation through cone programs.

**Relation:** Provides a general framework for differentiable optimization that our work complements. Our envelope gradient approach offers an alternative that avoids the linear system solves required by conic differentiation.

**Gap filled:** Generic differentiation through solvers; our approach exploits problem structure (support functions, duality) for more efficient gradients.

---

### 31. Bertsimas & Kallus (2020)
**Citation:** D. Bertsimas and N. Kallus, "From predictive to prescriptive analytics," *Management Science*, vol. 66, no. 3, pp. 1025–1044, 2020.

**Summary:** Develops the framework of prescriptive analytics that directly maps data to optimal decisions, bridging prediction and optimization. Establishes consistency and asymptotic optimality results.

**Relation:** Shares the goal of data-to-decisions optimization. Our work extends this to the robust optimization setting with uncertainty sets learned for decision quality.

---

### 32. Blondel, Berthet, Cuturi, et al. (2022)
**Citation:** M. Blondel, Q. Berthet, M. Cuturi, R. Frostig, S. Hoyer, F. Llinares-López, F. Pedregosa, and J.-P. Vert, "Efficient and modular implicit differentiation," in *Proc. Adv. Neural Inf. Process. Syst.*, vol. 35, pp. 5765–5776, 2022.

**Summary:** Develops a general framework for efficient implicit differentiation of fixed-point problems, optimization problems, and other implicit mappings. Provides modular building blocks for automatic differentiation.

**Relation:** Provides computational tools for implicit differentiation that could be used to implement our envelope gradients. Our approach is a specific instance of implicit differentiation via the envelope theorem.

---

### 33. Bolte, Le, Pauwels, & Silveti-Falls (2021)
**Citation:** J. Bolte, T. Le, E. Pauwels, and T. Silveti-Falls, "Nonsmooth implicit differentiation for machine learning and optimization," in *Proc. Adv. Neural Inf. Process. Syst.*, vol. 34, 2021.

**Summary:** Extends implicit differentiation to nonsmooth settings using Clarke's generalized Jacobian, enabling gradient-based learning through nonsmooth optimization problems.

**Relation:** Directly relevant to our Clarke subdifferential treatment (Definition 1, Theorem 1). When the dual optimizer is not unique, our envelope formula produces Clarke subgradients, consistent with this nonsmooth framework.

---

### 34. Mandi, Kotary, Berden, et al. (2024)
**Citation:** J. Mandi, J. Kotary, S. Berden, M. Mulamba, V. Bucarey, T. Guns, and F. Fioretto, "Decision-focused learning: foundations, state of the art, benchmark and future opportunities," *Journal of Artificial Intelligence Research*, vol. 80, pp. 1623–1701, 2024.

**Summary:** Comprehensive survey of decision-focused learning covering theoretical foundations, algorithmic approaches (differentiable optimization, surrogate losses, contrastive methods), benchmarks, and open problems.

**Relation:** Positions our work within the DFL landscape. Our envelope gradient approach is an instance of the "differentiable optimization" paradigm discussed here, but specialized to robust optimization with uncertainty set learning.

---

### 35. Sadana, Chenreddy, Delage, Forel, Frejinger, & Vidal (2025)
**Citation:** U. Sadana, A. Chenreddy, E. Delage, A. Forel, E. Frejinger, and T. Vidal, "A survey of contextual optimization methods for decision-making under uncertainty," *European Journal of Operational Research*, vol. 320, no. 2, pp. 271–289, 2025.

**Summary:** Surveys contextual optimization methods that integrate machine learning predictions into optimization under uncertainty, covering stochastic, robust, and distributionally robust formulations.

**Relation:** Our work is an instance of contextual robust optimization where the context (weather, system state) determines the uncertainty set shape via a neural network encoder.

---

### 36. El Balghiti, Elmachtoub, Grigas, & Tewari (2022)
**Citation:** O. El Balghiti, A. N. Elmachtoub, P. Grigas, and A. Tewari, "Generalization bounds in the predict-then-optimize framework," *Mathematics of Operations Research*, vol. 48, no. 4, pp. 2043–2065, 2022.

**Summary:** Establishes generalization bounds for the predict-then-optimize framework using Rademacher complexity, showing that decision quality on new data can be bounded from training performance.

**Relation:** Provides theoretical justification for the generalization of learned decision models. Our conformal calibration provides an alternative finite-sample guarantee (coverage rather than cost generalization).

---

## H) Learned Uncertainty Sets (Most Directly Related)

### 37. Wang, Becker, Van Parys, & Stellato (2023)
**Citation:** I. Wang, C. Becker, B. Van Parys, and B. Stellato, "Learning decision-focused uncertainty sets in robust optimization," *arXiv preprint arXiv:2305.19225*, 2023.

**Summary:** Proposes learning contextual uncertainty sets in robust optimization by minimizing expected decision cost subject to CVaR coverage constraints. Uses the nonsmooth conservative implicit function theorem for differentiation through the robust optimization layer.

**Relation:** Most directly related to our work. Key differences: (1) they differentiate through the RO solver via implicit differentiation, while we use envelope gradients from dual multipliers; (2) they use CVaR-based coverage, while we use conformal prediction for distribution-free coverage; (3) we provide a profiled gradient structure with an explicit quantile-sensitivity correction term.

**Gap filled:** Their approach requires differentiating through the solver; our envelope approach avoids this. We also provide conformal coverage guarantees rather than CVaR constraints.

---

### 38. Chenreddy & Delage (2024)
**Citation:** A. R. Chenreddy and E. Delage, "End-to-end conditional robust optimization," in *Proc. Conf. Uncertainty in Artificial Intelligence (UAI)*, PMLR, vol. 244, pp. 736–748, 2024.

**Summary:** Develops end-to-end training for conditional robust optimization, optimizing uncertainty set parameters while accounting for both decision quality and conditional coverage. Uses a logistic regression layer for differentiable coverage estimation.

**Relation:** Shares the goal of end-to-end conditional uncertainty set learning. Key differences: (1) we provide finite-sample conformal coverage guarantees under exchangeability, while they achieve conditional coverage empirically; (2) our envelope gradient approach avoids solver differentiation; (3) our three-way data split separates training, tuning, and calibration concerns.

**Gap filled:** Empirical conditional coverage; our conformal approach provides distribution-free marginal coverage guarantees.

---

### 39. Goerigk & Kurtz (2023)
**Citation:** M. Goerigk and J. Kurtz, "Data-driven robust optimization using deep neural networks," *Computers & Operations Research*, vol. 151, art. 106087, 2023.

**Summary:** Uses deep neural networks to predict uncertainty set parameters from contextual features, with the network trained on historical data to minimize robust optimization cost.

**Relation:** Shares the concept of neural-network-predicted uncertainty sets. Our framework adds conformal calibration for coverage guarantees and derives the profiled gradient structure including the quantile-sensitivity correction.

**Gap filled:** No formal coverage guarantees; our conformal calibration provides distribution-free coverage.

---

### 40. Ma, Ning, & Du (2024)
**Citation:** X. Ma, C. Ning, and W. Du, "Differentiable distributionally robust optimization layers," in *Proc. Int. Conf. Mach. Learn.*, PMLR, 2024.

**Summary:** Develops differentiable DRO layers for embedding mixed-integer DRO problems with parameterized ambiguity sets into learning pipelines. Uses a dual-view methodology for handling continuous and discrete decisions.

**Relation:** Addresses differentiable DRO layers, which is the DRO counterpart of our differentiable RO approach. We focus on geometric uncertainty sets with support function structure, while they handle distributional ambiguity sets.

**Gap filled:** Focused on DRO with ambiguity sets; our work handles RO with geometric uncertainty sets and provides conformal coverage.

---

### 41. Johnstone & Cox (2021)
**Citation:** C. Johnstone and B. Cox, "Conformal uncertainty sets for robust optimization," in *Proc. Conf. Probabilistic Prediction and Applications (COPA)*, PMLR, vol. 152, pp. 72–90, 2021.

**Summary:** Connects conformal prediction to robust optimization by constructing ellipsoidal uncertainty sets with finite-sample coverage guarantees using Mahalanobis distance as the conformity score.

**Relation:** Most directly related to our conformal calibration component. Their key idea — using conformal prediction to calibrate RO uncertainty sets — is shared with our approach. Key differences: (1) they use full conformal prediction; we use split conformal with a 3-way data split; (2) our sets are learned end-to-end rather than based on sample covariance; (3) we derive the profiled gradient including quantile sensitivity.

**Gap filled:** Conformal sets with fixed (sample) covariance; our sets have learned shape optimized for decision cost.

---

### 42. Dumouchelle, Julien, Kurtz, & Khalil (2024)
**Citation:** J. Dumouchelle, E. Julien, J. Kurtz, and E. B. Khalil, "Neur2RO: Neural two-stage robust optimization," in *Proc. Int. Conf. Learn. Representations (ICLR)*, 2024.

**Summary:** Uses deep learning to approximate the second-stage value function in two-stage robust optimization, enabling scalable solution via column-and-constraint generation with neural network surrogates.

**Relation:** Addresses computational scalability of two-stage RO using neural networks, complementary to our focus on learning uncertainty set geometry. Our work optimizes the uncertainty set; theirs approximates the solution algorithm.

---

## I) Conformal Prediction

### 43. Vovk, Gammerman, & Shafer (2005)
**Citation:** V. Vovk, A. Gammerman, and G. Shafer, *Algorithmic Learning in a Random World*. New York: Springer, 2005.

**Summary:** Foundational book on conformal prediction, establishing the theory of prediction with guaranteed coverage under exchangeability. Develops full and split conformal prediction frameworks.

**Relation:** Provides the theoretical foundation for our conformal calibration (Theorem 4). Our split conformal approach with the 3-way data split is a direct application of the framework developed here.

---

### 44. Romano, Patterson, & Candès (2019)
**Citation:** Y. Romano, E. Patterson, and E. Candès, "Conformalized quantile regression," in *Proc. Adv. Neural Inf. Process. Syst.*, vol. 32, 2019.

**Summary:** Combines conformal prediction with quantile regression to produce prediction intervals with guaranteed coverage while adapting to heteroscedasticity. Uses the CQR conformity score.

**Relation:** Demonstrates the use of conformal prediction for calibrating learned prediction regions, which parallels our use of conformal calibration for learned uncertainty sets. Our gauge score plays the role of CQR's conformity score.

---

### 45. Tibshirani, Foygel Barber, Candès, & Ramdas (2019)
**Citation:** R. J. Tibshirani, R. Foygel Barber, E. Candès, and A. Ramdas, "Conformal prediction under covariate shift," in *Proc. Adv. Neural Inf. Process. Syst.*, vol. 32, 2019.

**Summary:** Extends conformal prediction to handle covariate shift using weighted conformal prediction, where calibration samples are reweighted to match the test distribution.

**Relation:** Addresses distributional shift, which is relevant when our learned uncertainty sets are applied to conditions different from training. Our exchangeability assumption (Assumption 5) is the key condition; weighted conformal methods could extend our approach to non-exchangeable settings.

---

### 46. Angelopoulos & Bates (2023)
**Citation:** A. N. Angelopoulos and S. Bates, "Conformal prediction: a gentle introduction," *Foundations and Trends in Machine Learning*, vol. 16, no. 4, pp. 494–591, 2023.

**Summary:** Tutorial introduction to conformal prediction covering split conformal, full conformal, and various extensions. Emphasizes practical aspects and recent developments.

**Relation:** Provides accessible exposition of the conformal prediction tools we use. Our split conformal calibration (Section III-D) follows the standard framework presented here.

---

## J) Convex Analysis and Sensitivity Theory

### 47. Rockafellar (1970)
**Citation:** R. T. Rockafellar, *Convex Analysis*. Princeton, NJ: Princeton University Press, 1970.

**Summary:** Foundational treatise on convex analysis, including support functions, gauge functions, conjugate duality, and the theory of convex optimization.

**Relation:** Provides the mathematical foundations for our gauge-based uncertainty sets, support function calculus, and duality theory used throughout the paper.

---

### 48. Bertsekas (1999)
**Citation:** D. P. Bertsekas, *Nonlinear Programming*, 2nd ed. Belmont, MA: Athena Scientific, 1999.

**Summary:** Comprehensive textbook covering nonlinear optimization theory including Lagrange duality, sensitivity analysis, and the relationship between dual multipliers and constraint sensitivity.

**Relation:** Provides the duality and sensitivity analysis foundations for our envelope gradient approach. The connection between dual multipliers and constraint sensitivity is central to Theorems 1–2.

---

### 49. Bonnans & Shapiro (2000)
**Citation:** J. F. Bonnans and A. Shapiro, *Perturbation Analysis of Optimization Problems*. New York: Springer, 2000.

**Summary:** Comprehensive treatment of sensitivity and stability analysis for optimization problems, including parametric optimization, directional derivatives of value functions, and connections to duality.

**Relation:** Provides the theoretical foundation for our envelope theorem approach. The parametric sensitivity results (value function derivatives via dual multipliers) underpin Theorems 1–2.

---

### 50. Clarke (1990)
**Citation:** F. H. Clarke, *Optimization and Nonsmooth Analysis*. Philadelphia: SIAM, 1990 (reprint of 1983 Wiley edition).

**Summary:** Foundational text on nonsmooth optimization, introducing the Clarke subdifferential (generalized gradient) and establishing calculus rules for locally Lipschitz functions.

**Relation:** The Clarke subdifferential (Definition 1) is central to our envelope gradient results when the dual optimizer is not unique. Our Theorems 1–2 produce Clarke subgradients in the general case.

---

## Summary of Gaps Filled by Our Work

| Existing Literature | Gap | Our Contribution |
|---|---|---|
| Traditional RO (Ben-Tal, Bertsimas) | Fixed uncertainty set geometry | Learned gauge-based sets from data |
| Decision-focused learning (Donti, Amos) | KKT differentiation through solver | Envelope gradients from duals only |
| Data-driven RO (Bertsimas et al. 2018) | Sets optimized for statistical fit | Sets optimized for decision cost |
| Conformal prediction (Vovk, Romano) | Applied to prediction intervals | Applied to RO uncertainty sets with profiled gradients |
| Learned sets (Wang et al. 2023) | Solver differentiation + CVaR coverage | Envelope gradients + conformal coverage |
| Power systems RO (Bertsimas et al. 2013) | Fixed polyhedral sets | Learned ellipsoidal sets capturing correlations |
| DRO (Esfahani & Kuhn 2018) | Distributional ambiguity sets | Geometric uncertainty sets with support function structure |

---

*Total papers reviewed: 50*
*Categories covered: 10*
