import tensorflow as tf
import keras
from keras import layers
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

@keras.saving.register_keras_serializable()
def ctc_batch_cost(y_true, y_pred, input_length, label_length):
    label_length = tf.cast(tf.squeeze(label_length, axis=-1), dtype="int32")
    input_length = tf.cast(tf.squeeze(input_length, axis=-1), dtype="int32")
    sparse_labels = tf.cast(
        ctc_label_dense_to_sparse(y_true, label_length), dtype="int32"
    )

    y_pred = tf.math.log(tf.transpose(y_pred, perm=[1, 0, 2]) + keras.backend.epsilon())

    return tf.expand_dims(
        tf.compat.v1.nn.ctc_loss(
            inputs=y_pred, labels=sparse_labels, sequence_length=input_length
        ),
        1,
    )

@keras.saving.register_keras_serializable()
def ctc_label_dense_to_sparse(labels, label_lengths):
    label_shape = tf.shape(labels)
    num_batches_tns = tf.stack([label_shape[0]])
    max_num_labels_tns = tf.stack([label_shape[1]])

    def range_less_than(old_input, current_input):
        return tf.expand_dims(tf.range(tf.shape(old_input)[1]), 0) < tf.fill(
            max_num_labels_tns, current_input
        )

    init = tf.cast(tf.fill([1, label_shape[1]], 0), dtype="bool")
    dense_mask = tf.compat.v1.scan(
        range_less_than, label_lengths, initializer=init, parallel_iterations=1
    )
    dense_mask = dense_mask[:, 0, :]

    label_array = tf.reshape(
        tf.tile(tf.range(0, label_shape[1]), num_batches_tns), label_shape
    )
    label_ind = tf.compat.v1.boolean_mask(label_array, dense_mask)

    batch_array = tf.transpose(
        tf.reshape(
            tf.tile(tf.range(0, label_shape[0]), max_num_labels_tns),
            tf.reverse(label_shape, [0]),
        )
    )
    batch_ind = tf.compat.v1.boolean_mask(batch_array, dense_mask)
    indices = tf.transpose(
        tf.reshape(tf.concat([batch_ind, label_ind], axis=0), [2, -1])
    )

    vals_sparse = tf.compat.v1.gather_nd(labels, indices)

    return tf.SparseTensor(
        tf.cast(indices, dtype="int64"),
        vals_sparse,
        tf.cast(label_shape, dtype="int64"),
    )

@keras.saving.register_keras_serializable()
class CTCLayer(layers.Layer):
    def __init__(self, name=None, trainable=True, dtype=None, **kwargs):
        super().__init__(name=name, trainable=trainable, dtype=dtype, **kwargs)
        self.loss_fn = ctc_batch_cost

    def call(self, y_true, y_pred):
        batch_len = tf.cast(tf.shape(y_true)[0], dtype="int64")
        input_length = tf.cast(tf.shape(y_pred)[1], dtype="int64")
        label_length = tf.cast(tf.shape(y_true)[1], dtype="int64")

        input_length = input_length * tf.ones(shape=(batch_len, 1), dtype="int64")
        label_length = label_length * tf.ones(shape=(batch_len, 1), dtype="int64")

        loss = self.loss_fn(y_true, y_pred, input_length, label_length)
        self.add_loss(loss)

        return y_pred

    def get_config(self):
        config = super().get_config()
        return config

class CaptchaPredictor:
    def __init__(self, model_path='captcha.keras', img_width=130, img_height=50):
        self.img_width = img_width
        self.img_height = img_height
        
        # Register the custom objects
        custom_objects = {
            'CTCLayer': CTCLayer,
            'ctc_batch_cost': ctc_batch_cost,
            'ctc_label_dense_to_sparse': ctc_label_dense_to_sparse
        }
        
        # Load the model with custom objects
        self.model = keras.models.load_model(model_path, custom_objects=custom_objects)
        
        # Extract prediction model (without CTC layer)
        self.prediction_model = keras.models.Model(
            self.model.input[0], 
            self.model.get_layer(name="dense2").output
        )
        
        # Load vocabulary
        self.char_to_num = self._load_vocabulary()
        self.num_to_char = layers.StringLookup(
            vocabulary=self.char_to_num.get_vocabulary(), 
            mask_token=None, 
            invert=True
        )

    def _load_vocabulary(self):
        """Load the character vocabulary from vocab.txt"""
        try:
            with open("vocab.txt", "r") as f:
                vocab = [line.strip() for line in f]
            return layers.StringLookup(vocabulary=vocab, mask_token=None)
        except FileNotFoundError:
            raise FileNotFoundError("vocab.txt not found. Please ensure the vocabulary file exists.")

    def preprocess_image(self, image_path):
        """Preprocess a single image for prediction"""
        img = tf.io.read_file(image_path)
        img = tf.io.decode_png(img, channels=1)
        img = tf.image.convert_image_dtype(img, tf.float32)
        img = tf.image.resize(img, [self.img_height, self.img_width])
        img = tf.transpose(img, perm=[1, 0, 2])
        return tf.expand_dims(img, axis=0)

    def ctc_decode(self, y_pred, input_length, greedy=True, beam_width=100, top_paths=1):
        """CTC decoder implementation"""
        input_shape = tf.shape(y_pred)
        num_samples, num_steps = input_shape[0], input_shape[1]
        y_pred = tf.math.log(tf.transpose(y_pred, perm=[1, 0, 2]) + keras.backend.epsilon())
        input_length = tf.cast(input_length, dtype="int32")

        if greedy:
            decoded, log_prob = tf.nn.ctc_greedy_decoder(
                inputs=y_pred,
                sequence_length=input_length
            )
        else:
            decoded, log_prob = tf.compat.v1.nn.ctc_beam_search_decoder(
                inputs=y_pred,
                sequence_length=input_length,
                beam_width=beam_width,
                top_paths=top_paths
            )

        decoded_dense = []
        for st in decoded:
            st = tf.SparseTensor(st.indices, st.values, (num_samples, num_steps))
            decoded_dense.append(tf.sparse.to_dense(sp_input=st, default_value=-1))
        return decoded_dense, log_prob

    def decode_predictions(self, pred, max_length):
        """Decode the raw predictions into text"""
        input_len = np.ones(pred.shape[0]) * pred.shape[1]
        results = self.ctc_decode(pred, input_length=input_len, greedy=True)[0][0][:, :max_length]
        
        output_text = []
        for res in results:
            text = tf.strings.reduce_join(self.num_to_char(res)).numpy().decode("utf-8")
            output_text.append(text)
        return output_text
    
   
    def predict(self, image_path, max_length=5):
        """Predict text from a single image"""
        processed_img = self.preprocess_image(image_path)
        pred = self.prediction_model.predict(processed_img, verbose=0)
        return self.decode_predictions(pred, max_length)[0]

    def predict_batch(self, image_paths, max_length=5):
        """Predict text from a batch of images"""
        processed_images = tf.concat([self.preprocess_image(img) for img in image_paths], axis=0)
        preds = self.prediction_model.predict(processed_images, verbose=0)
        return self.decode_predictions(preds, max_length)

    def visualize_predictions(self, image_paths, figsize=(15, 5)):
        """Visualize predictions with images"""
        predictions = self.predict_batch(image_paths)
        n_images = len(image_paths)
        rows = (n_images + 3) // 4
        cols = min(4, n_images)
        
        _, ax = plt.subplots(rows, cols, figsize=figsize)
        if rows == 1:
            ax = [ax]
        if cols == 1:
            ax = [[a] for a in ax]
            
        for i, (img_path, pred) in enumerate(zip(image_paths, predictions)):
            img = tf.io.decode_png(tf.io.read_file(img_path), channels=1)
            row, col = i // 4, i % 4
            ax[row][col].imshow(img.numpy().squeeze(), cmap='gray')
            ax[row][col].set_title(f'Prediction: {pred}')
            ax[row][col].axis('off')
        
        plt.tight_layout()
        plt.show()

