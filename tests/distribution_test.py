# coding=utf-8
# Copyright 2019 The Google Research Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for distribution.py."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import scipy.stats
import torch
from robust_loss_pytorch import distribution


class TestDistribution:

  def setUp(self):
    torch.manual_seed(0)
    np.random.seed(0)

  def testSplineCurveIsC1Smooth(self):
    """Tests that partition_spline_curve() and its derivative are continuous."""
    x1 = np.linspace(0., 8., 10000, dtype=np.float64)
    x2 = x1 + 1e-7

    var_x1 = torch.autograd.Variable(torch.tensor(x1), requires_grad=True)
    y1 = distribution.partition_spline_curve(var_x1)
    sum_y1 = torch.sum(y1)
    sum_y1.backward()
    dy1 = var_x1.grad.detach().numpy()
    y1 = y1.detach().numpy()

    var_x2 = torch.autograd.Variable(torch.tensor(x2), requires_grad=True)
    y2 = distribution.partition_spline_curve(var_x2)
    sum_y2 = torch.sum(y2)
    sum_y2.backward()
    dy2 = var_x2.grad.detach().numpy()
    y2 = y2.detach().numpy()

    np.testing.assert_allclose(y1, y2, atol=1e-6, rtol=1e-6)
    np.testing.assert_allclose(dy1, dy2, atol=1e-6, rtol=1e-6)

  def testAnalyaticalPartitionIsCorrect(self):
    """Tests _analytical_base_partition_function against some golden data."""
    # Here we enumerate a set of positive rational numbers n/d alongside
    # numerically approximated values of Z(n / d) up to 10 digits of precision,
    # stored as (n, d, Z(n/d)). This was generated with an external mathematica
    # script.
    ground_truth_rational_partitions = (
        (1, 7, 4.080330073), (1, 6, 4.038544331), (1, 5, 3.984791180),
        (1, 4, 3.912448576), (1, 3, 3.808203509), (2, 5, 3.735479786),
        (3, 7, 3.706553276), (1, 2, 3.638993131), (3, 5, 3.553489270),
        (2, 3, 3.501024540), (3, 4, 3.439385624), (4, 5, 3.404121259),
        (1, 1, 3.272306973), (6, 5, 3.149249092), (5, 4, 3.119044506),
        (4, 3, 3.068687433), (7, 5, 3.028084866), (3, 2, 2.965924889),
        (8, 5, 2.901059987), (5, 3, 2.855391798), (7, 4, 2.794052016),
        (7, 3, 2.260434598), (5, 2, 2.218882601), (8, 3, 2.190349858),
        (3, 1, 2.153202857), (4, 1, 2.101960916), (7, 2, 2.121140098),
        (5, 1, 2.080000512), (9, 2, 2.089161164), (6, 1, 2.067751267),
        (7, 1, 2.059929623), (8, 1, 2.054500222), (10, 3, 2.129863884),
        (11, 3, 2.113763384), (13, 3, 2.092928254), (14, 3, 2.085788350),
        (16, 3, 2.075212740), (11, 2, 2.073116001), (17, 3, 2.071185791),
        (13, 2, 2.063452243), (15, 2, 2.056990258))  # pyformat: disable
    for numer, denom, z_true in ground_truth_rational_partitions:
      z = distribution.analytical_base_partition_function(numer, denom)
      np.testing.assert_allclose(z, z_true, atol=1e-9, rtol=1e-9)

  def testSplineCurveInverseIsCorrect(self):
    """Tests that the inverse curve is indeed the inverse of the curve."""
    x_knot = np.arange(0, 16, 0.01, dtype=np.float64)
    alpha = distribution.inv_partition_spline_curve(x_knot)
    x_recon = distribution.partition_spline_curve(alpha)
    np.testing.assert_allclose(x_recon, x_knot)

  def _log_partition_infinity_is_accurate(self, float_dtype):
    """Tests that the partition function is accurate at infinity."""
    alpha = float_dtype(float('inf'))
    log_z_true = np.float64(0.70526025442)  # From mathematica.
    log_z = distribution.log_base_partition_function(alpha)
    np.testing.assert_allclose(log_z, log_z_true, atol=1e-7, rtol=1e-7)

  def testLogPartitionInfinityIsAccurateSingle(self):
    self._log_partition_infinity_is_accurate(np.float32)

  def testLogPartitionInfinityIsAccurateDouble(self):
    self._log_partition_infinity_is_accurate(np.float64)

  def _log_partition_fractions_are_accurate(self, float_dtype):
    """Test that the partition function is correct for [0/11, ... 22/11]."""
    numers = range(0, 23)
    denom = 11
    log_zs_true = [
        np.log(distribution.analytical_base_partition_function(n, denom))
        for n in numers
    ]
    log_zs = distribution.log_base_partition_function(
        float_dtype(np.array(numers)) / float_dtype(denom))
    np.testing.assert_allclose(log_zs, log_zs_true, atol=1e-7, rtol=1e-7)

  def testLogPartitionFractionsAreAccurateSingle(self):
    self._log_partition_fractions_are_accurate(np.float32)

  def testLogPartitionFractionsAreAccurateDouble(self):
    self._log_partition_fractions_are_accurate(np.float64)

  def _alpha_zero_samples_match_a_cauchy_distribution(self, float_dtype):
    """Tests that samples when alpha=0 match a Cauchy distribution."""
    num_samples = 16384
    scale = float_dtype(1.7)
    samples = distribution.draw_samples(
        np.zeros(num_samples, dtype=float_dtype),
        scale * np.ones(num_samples, dtype=float_dtype))
    # Perform the Kolmogorov-Smirnov test against a Cauchy distribution.
    ks_statistic = scipy.stats.kstest(samples, 'cauchy',
                                      (0., scale * np.sqrt(2.))).statistic
    np.testing.assert_(ks_statistic < 0.01)

  def testAlphaZeroSamplesMatchACauchyDistributionSingle(self):
    self._alpha_zero_samples_match_a_cauchy_distribution(np.float32)

  def testAlphaZeroSamplesMatchACauchyDistributionDouble(self):
    self._alpha_zero_samples_match_a_cauchy_distribution(np.float64)

  def _alpha_two_samples_match_a_normal_distribution(self, float_dtype):
    """Tests that samples when alpha=2 match a normal distribution."""
    num_samples = 16384
    scale = float_dtype(1.7)
    samples = distribution.draw_samples(
        2. * np.ones(num_samples, dtype=float_dtype),
        scale * np.ones(num_samples, dtype=float_dtype))
    # Perform the Kolmogorov-Smirnov test against a normal distribution.
    ks_statistic = scipy.stats.kstest(samples, 'norm', (0., scale)).statistic
    np.testing.assert_(ks_statistic < 0.01)

  def testAlphaTwoSamplesMatchANormalDistributionSingle(self):
    self._alpha_two_samples_match_a_normal_distribution(np.float32)

  def testAlphaTwoSamplesMatchANormalDistributionDouble(self):
    self._alpha_two_samples_match_a_normal_distribution(np.float64)

  def _alpha_zero_nlls_match_a_cauchy_distribution(self, float_dtype):
    """Tests that NLLs when alpha=0 match a Cauchy distribution."""
    x = np.linspace(-10., 10, 1000, dtype=float_dtype)
    scale = np.array(1.7, float_dtype)
    alpha = np.array(0., float_dtype)
    nll = distribution.nllfun(x, alpha, scale)
    nll_true = -scipy.stats.cauchy(0., scale * np.sqrt(2.)).logpdf(x)
    np.testing.assert_allclose(nll, nll_true, atol=1e-6, rtol=1e-6)

  def testAlphaZeroNllsMatchACauchyDistributionSingle(self):
    self._alpha_zero_nlls_match_a_cauchy_distribution(np.float32)

  def testAlphaZeroNllsMatchACauchyDistributionDouble(self):
    self._alpha_zero_nlls_match_a_cauchy_distribution(np.float64)

  def _alpha_two_nlls_match_a_normal_distribution(self, float_dtype):
    """Tests that NLLs when alpha=2 match a normal distribution."""
    x = np.linspace(-10., 10, 1000, dtype=float_dtype)
    scale = np.array(1.7, float_dtype)
    alpha = np.array(2., float_dtype)
    nll = distribution.nllfun(x, alpha, scale)
    nll_true = -scipy.stats.norm(0., scale).logpdf(x)
    np.testing.assert_allclose(nll, nll_true, atol=1e-6, rtol=1e-6)

  def testAlphaTwoNllsMatchANormalDistributionSingle(self):
    self._alpha_two_nlls_match_a_normal_distribution(np.float32)

  def testAlphaTwoNllsMatchANormalDistributionDouble(self):
    self._alpha_two_nlls_match_a_normal_distribution(np.float64)

  def _pdf_integrates_to_one(self, float_dtype):
    """Tests that the PDF integrates to 1 for different alphas."""
    alphas = np.exp(np.linspace(-4., 8., 8, dtype=float_dtype))
    scale = float_dtype(1.7)
    x = np.arange(-128., 128., 1 / 256., dtype=float_dtype) * scale
    for alpha in alphas:
      nll = distribution.nllfun(x, np.array(alpha),
                                np.array(scale)).detach().numpy()
      pdf_sum = np.sum(np.exp(-nll)) * (x[1] - x[0])
      np.testing.assert_allclose(pdf_sum, 1., atol=0.005, rtol=0.005)

  def testPdfIntegratesToOneSingle(self):
    self._pdf_integrates_to_one(np.float32)

  def testPdfIntegratesToOneDouble(self):
    self._pdf_integrates_to_one(np.float64)

  def _nllfun_preserves_dtype(self, float_dtype):
    """Checks that the loss's output has the same precision as its input."""
    n = 16
    x = float_dtype(np.random.normal(size=n))
    alpha = float_dtype(np.exp(np.random.normal(size=n)))
    scale = float_dtype(np.exp(np.random.normal(size=n)))
    y = distribution.nllfun(x, alpha, scale).detach().numpy()
    np.testing.assert_(y.dtype, float_dtype)

  def testNllfunPreservesDtypeSingle(self):
    self._nllfun_preserves_dtype(np.float32)

  def testNllfunPreservesDtypeDouble(self):
    self._nllfun_preserves_dtype(np.float64)

  def _sampling_preserves_dtype(self, float_dtype):
    """Checks that sampling's output has the same precision as its input."""
    n = 16
    alpha = float_dtype(np.exp(np.random.normal(size=n)))
    scale = float_dtype(np.exp(np.random.normal(size=n)))
    y = distribution.draw_samples(alpha, scale).detach().numpy()
    np.testing.assert_(y.dtype, float_dtype)

  def testSamplingPreservesDtypeSingle(self):
    self._sampling_preserves_dtype(np.float32)

  def testSamplingPreservesDtypeDouble(self):
    self._sampling_preserves_dtype(np.float64)


if __name__ == '__main__':
  np.testing.run_module_suite()
