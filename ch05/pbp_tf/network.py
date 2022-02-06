import numpy as np

# import theano
#
# import theano.tensor as T
import tensorflow as tf
from ch05.pbp_tf import network_layer


class Network:
    def __init__(self, m_w_init, v_w_init, a_init, b_init):
        # We create the different layers
        self.layers = []
        idx = 0
        if len(m_w_init) > 1:
            for idx, (m_w, v_w) in enumerate(zip(m_w_init[:-1], v_w_init[:-1])):
                self.layers.append(network_layer.NetworkLayer(m_w, v_w, True, layer_index=idx))
        self.layers.append(
            network_layer.NetworkLayer(m_w_init[-1], v_w_init[-1], False, layer_index=idx+1)
        )

        # We create mean and variance parameters from all layers
        self.params_m_w = []
        self.params_v_w = []
        self.params_w = []
        for layer in self.layers:
            self.params_m_w.append(layer.m_w)
            self.params_v_w.append(layer.v_w)
            self.params_w.append(layer.w)

        # We create the theano variables for a and b
        self.a = tf.constant(float(a_init), dtype=tf.float64)
        self.b = tf.constant(float(b_init), dtype=tf.float64)
        assert a_init == 6.0
        assert b_init == 6.0
        print("a and b look good.")

        # self.a = theano.shared(float(a_init))
        # self.b = theano.shared(float(b_init))

    def output_deterministic(self, x):
        # Recursively compute output
        for layer in self.layers:
            x = layer.output_deterministic(x)
        return x

    def output_probabilistic(self, m):
        v = tf.zeros_like(m)
        # Recursively compute output
        for layer in self.layers:
            print("going through layer")
            m, v = layer.output_probabilistic(m, v)
        return m, v

    def logZ_Z1_Z2(self, x, y):
        m, v = self.output_probabilistic(x)

        v_final = v + self.b / (self.a - 1)
        v_final1 = v + self.b / self.a
        v_final2 = v + self.b / (self.a + 1)

        logZ = -0.5 * (tf.math.log(v_final) + (y - m) ** 2 / v_final)
        logZ1 = -0.5 * (tf.math.log(v_final1) + (y - m) ** 2 / v_final1)
        logZ2 = -0.5 * (tf.math.log(v_final2) + (y - m) ** 2 / v_final2)
        return logZ, logZ1, logZ2

    def log_Z(self, x, y):
        m, v = self.output_probabilistic(x)
        # import ipdb
        # ipdb.set_trace()
        v_final = v + self.b / (self.a - 1)
        return -0.5 * (tf.math.log(v_final) + (y - m) ** 2 / v_final)

    def log_Z1(self, x, y):
        m, v = self.output_probabilistic(x)
        v_final1 = v + self.b / self.a
        return -0.5 * (tf.math.log(v_final1) + (y - m) ** 2 / v_final1)

    def log_Z2(self, x, y):
        m, v = self.output_probabilistic(x)
        v_final2 = v + self.b / (self.a + 1)
        return -0.5 * (tf.math.log(v_final2) + (y - m) ** 2 / v_final2)

    def generate_updates(self, x, y):
        raise Exception("Something here should be fixed.")
        updates = []
        for i in range(len(self.params_m_w)):
            updates.append(
                (
                    self.params_m_w[i],
                    self.params_m_w[i]
                    + self.params_v_w[i] * tf.gradients(lo_1, self.params_m_w[i]),
                )
            )
            updates.append(
                (
                    self.params_v_w[i],
                    self.params_v_w[i]
                    - self.params_v_w[i] ** 2
                    * (
                        tf.gradients(lo_1, self.params_m_w[i]) ** 2
                        - 2 * tf.gradients(lo_1, self.params_v_w[i])
                    ),
                )
            )

        updates.append(
            (
                self.a,
                1.0 / (tf.math.exp(lo_3 - 2 * lo_2 + lo_1) * (self.a + 1) / self.a - 1.0),
            )
        )
        updates.append(
            (
                self.b,
                1.0
                / (
                    tf.math.exp(lo_3 - lo_2) * (self.a + 1) / (self.b)
                    - tf.math.exp(lo_2 - lo_1) * self.a / self.b
                ),
            )
        )

        return updates

    def get_params(self):
        m_w = []
        v_w = []
        for layer in self.layers:
            m_w.append(layer.m_w)
            v_w.append(layer.v_w)

        return {
            "m_w": m_w,
            "v_w": v_w,
            "a": self.a,
            "b": self.b,
        }

    def set_params(self, params):
        for i in range(len(self.layers)):
            self.layers[i].m_w.set_value(params["m_w"][i])
            self.layers[i].v_w.set_value(params["v_w"][i])

        self.a.set_value(params["a"])
        self.b.set_value(params["b"])

    def remove_invalid_updates(self, new_params, old_params):

        m_w_new = new_params["m_w"]
        v_w_new = new_params["v_w"]
        m_w_old = old_params["m_w"]
        v_w_old = old_params["v_w"]

        for i in range(len(self.layers)):
            index1 = np.where(v_w_new[i] <= 1e-100)
            index2 = np.where(np.logical_or(np.isnan(m_w_new[i]), np.isnan(v_w_new[i])))

            index = [
                np.concatenate((index1[0], index2[0])),
                np.concatenate((index1[1], index2[1])),
            ]

            if len(index[0]) > 0:
                m_w_new[i][index] = m_w_old[i][index]
                v_w_new[i][index] = v_w_old[i][index]

    def sample_w(self):

        w = []
        for i in range(len(self.layers)):
            w.append(
                self.params_m_w[i].get_value()
                + np.random.randn(
                    self.params_m_w[i].get_value().shape[0],
                    self.params_m_w[i].get_value().shape[1],
                )
                * np.sqrt(self.params_v_w[i].get_value())
            )

        for i in range(len(self.layers)):
            self.params_w[i].set_value(w[i])