"""
An novel image denoising method using a generative adverserial network which uses
kernal maxmimum mean discrepancy (MMD-GAN).

Inspired by [https://arxiv.org/abs/1705.08584] and [https://arxiv.org/abs/1801.01401].

Isak Persson
Wei Hu

15 August 2019
"""

import tensorflow as tf
import kernels
import utils

from models.mmd_gan_model import gen_cnn_model_fn, d_decoder, d_encoder


EPOCHS = 10000
GEN_LR = 0.001
DIS_LR = 0.001
BATCH_SIZE = 64
STDV = 25  # The standard deviation used for the gaussian noise.

# MMD Loss Hyperparameters:
LAMBDA_X = 8.0
LAMBDA_Y = 8.0


def train(gen_loss, dis_loss, summary):
    """ The main procedure for training the model. On every tenth step, statistics about
    the how the training is progressing is printed out.

    Args:
        loss: the loss function which the model is aiming to minimize.
        original: the original image which is composed of a batch of patches.
        noisy_image: the original image with Gaussian noise added.
        output: the noise generated by the neural network.
    """
    # Gets all the discriminator's variables
    dis_var = [
        var
        for var in tf.trainable_variables()
        if "d_decoder" in var.name or "d_encoder" in var.name
    ]
    # Creates an optimizer for the discriminator to minimize a loss
    dis_train_op = tf.compat.v1.train.AdamOptimizer(learning_rate=DIS_LR).minimize(
        loss=dis_loss,
        var_list=dis_var,
        global_step=tf.compat.v1.train.get_global_step(),
    )

    # Gets all the generator's variables
    gen_var = [var for var in tf.trainable_variables() if "generator" in var.name]
    # Creates an optimizer for the generator to minimize a loss
    gen_train_op = tf.compat.v1.train.AdamOptimizer(learning_rate=GEN_LR).minimize(
        loss=gen_loss,
        var_list=gen_var,
        global_step=tf.compat.v1.train.get_global_step(),
    )

    with tf.compat.v1.Session() as sess:

        if ARGS.initialize:
            sess.run(tf.global_variables_initializer())
        else:
            tf.compat.v1.train.Saver().restore(sess, "./models/trained/mmd_gan.ckpt")

        writer = tf.summary.FileWriter("./log/mmd_gan", sess.graph)

        for step in range(EPOCHS):

            _summary, _, _ = sess.run([summary, dis_train_op, gen_train_op])

            writer.add_summary(_summary, step)

            if step % 10 == 0:
                tf.compat.v1.train.Saver().save(sess, "./models/trained/mmd_gan.ckpt")


def main():
    """ Implements the deep convolutional neural network for denoising images based on
    the paper by Zhang et al.

    There are two modes. During training mode, the model takes in a batch of 64 by 64
    image patches from the training set. During evaluation mode, the the model attempts
    to denoise images of varying sizes from the test set.
    """

    iterator = utils.create_dataset_iterator(utils.PATCHES)
    original = iterator.get_next()

    # Generates Gaussian noise and adds it to the image.
    noise = utils.scale(utils.gaussian_noise(tf.shape(original), 0, STDV))
    noisy_image = original + noise
    y = gen_cnn_model_fn(noisy_image)

    # Encodes the ground truth and the noisy image to be used in the loss function.
    f_enc_x_d = d_encoder(original, batch_size=BATCH_SIZE, reuse=False)
    f_enc_y_d = d_encoder(y, batch_size=BATCH_SIZE, reuse=True)
    # Decodes the encoded ground truth and the noisy image for the regularization term.
    f_dec_x_d = d_decoder(f_enc_x_d, batch_size=BATCH_SIZE, reuse=False)
    f_dec_y_d = d_decoder(f_enc_y_d, batch_size=BATCH_SIZE, reuse=True)

    # Regularization Loss. This loss is created to push the discriminator's encoder to be injective.
    l2_x = tf.losses.mean_squared_error(original, f_dec_x_d)
    l2_y = tf.losses.mean_squared_error(y, f_dec_y_d)

    mmd_loss = kernels.mmd2(tf.squeeze(f_enc_x_d), tf.squeeze(f_enc_y_d))

    gen_loss = mmd_loss
    tot_loss = mmd_loss - LAMBDA_X * l2_x - LAMBDA_Y * l2_y

    # Creates summary for tensorboard
    image_summaries = {
        "Original Image": original,
        "Noisy Image": noisy_image,
        "Generated Noise": noisy_image - y,
        "Denoised Image": y,
    }
    scalar_summaries = {
        "PSNR": utils.psnr(tf.squeeze(original), tf.squeeze(y)),
        "Generator Loss": gen_loss,
        "Discriminator Loss": -tot_loss,
        "Brightest Pixel in Noise": tf.reduce_max(noisy_image - y),
        "Darkest Pixel in Noise": tf.reduce_min(noisy_image - y),
    }
    summary = utils.create_summary(image_summaries, scalar_summaries)

    train(gen_loss, -tot_loss, summary)


if __name__ == "__main__":
    ARGS = utils.get_args()
    main()
