"""
A method based on generative...

Isak Persson
Wei Hu

5 August 2019
"""


import tensorflow as tf
import utils

from models.gan_model import gen_cnn_model_fn, dis_cnn_model_fn

EPOCHS = 10000
GEN_LR = 0.001
DIS_LR = 0.002
BATCH_SIZE = 64
STDV = 25  # The standard deviation used for the gaussian noise.


def train(gen_loss, dis_loss, summary):
    """ The main procedure for training the model. On every tenth step, statistics about
    the how the training is progressing is printed out.

    Args:
        loss: the loss function which the model is aiming to minimize.
        original: the original image which is composed of a batch of patches.
        noisy_image: the original image with Gaussian noise added.
        output: the noise generated by the neural network.
    """
    dis_var = [var for var in tf.trainable_variables() if "discriminator" in var.name]
    dis_train_op = tf.compat.v1.train.AdamOptimizer(learning_rate=DIS_LR).minimize(
        loss=dis_loss,
        var_list=dis_var,
        global_step=tf.compat.v1.train.get_global_step(),
    )

    gen_var = [var for var in tf.trainable_variables() if "generator" in var.name]
    gen_train_op = tf.compat.v1.train.AdamOptimizer(learning_rate=GEN_LR).minimize(
        loss=gen_loss,
        var_list=gen_var,
        global_step=tf.compat.v1.train.get_global_step(),
    )

    with tf.compat.v1.Session() as sess:

        if ARGS.initialize:
            sess.run(tf.global_variables_initializer())
        else:
            tf.compat.v1.train.Saver().restore(sess, "./models/trained/gan.ckpt")

        writer = tf.summary.FileWriter("./log/gan", sess.graph)

        for step in range(EPOCHS):

            _summary, _, _ = sess.run([summary, dis_train_op, gen_train_op])

            writer.add_summary(_summary, step)

            if step % 10 == 0:
                tf.compat.v1.train.Saver().save(sess, "./models/trained/gan.ckpt")


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
    gen_output = gen_cnn_model_fn(noisy_image)

    discriminator_layers = {}
    dis_ground = dis_cnn_model_fn(original, discriminator_layers)
    dis_gen = dis_cnn_model_fn(gen_output, discriminator_layers)
    # Loss Definitions
    gen_loss = -tf.reduce_mean(tf.log(tf.clip_by_value(dis_gen, 10e-10, 1.0)))
    dis_loss = -tf.reduce_mean(
        tf.log(tf.clip_by_value(dis_ground, 10e-10, 1.0))
        + tf.log(tf.clip_by_value(1.0 - dis_gen, 10e-10, 1.0))
    )

    image_summaries = {
        "Original Image": original,
        "Noisy Image": noisy_image,
        "Generated Noise": noisy_image - gen_output,
        "Denoised Image": gen_output,
    }
    scalar_summaries = {
        "PSNR": utils.psnr(tf.squeeze(original), tf.squeeze(gen_output)),
        "Generator Loss": gen_loss,
        "Discriminator Loss": dis_loss,
        "Brightest Pixel in Noise": tf.reduce_max(noisy_image - gen_output) * 255,
        "Darkest Pixel in Noise": tf.reduce_min(noisy_image - gen_output) * 255,
    }
    summary = utils.create_summary(image_summaries, scalar_summaries)
    train(gen_loss, dis_loss, summary)


if __name__ == "__main__":
    ARGS = utils.get_args()
    main()