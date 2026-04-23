# Hyperparameters optimized for NVIDIA RTX 4060 8GB

VOCAB_SIZE      = 50304 #Defines the number of unique tokens (words/subwords) in your tokenizer.
CONTEXT_LENGTH  = 512 #Maximum number of tokens the model can "see" at once.
N_EMBED         = 768 #Size of each token’s vector (embedding dimension).
N_HEAD          = 12 #Number of attention heads in multi-head attention.
N_BLOCKS        = 12 #Number of transformer layers stacked.

TRAIN_PATH = "data/train/pile_train.h5"
DEV_PATH   = "data/val/pile_dev.h5"

T_BATCH_SIZE     = 8   #8 Number of sequences processed at once.
T_CONTEXT_LENGTH = 256  #Training sequence length
T_TRAIN_STEPS    = 500_000  #Total number of training iterations.
T_EVAL_STEPS     = 500 #Evaluate every N steps during training.
T_EVAL_ITERS     = 100 #Number of batches to evaluate on during each evaluation phase (for validation loss estimation).
T_LR             = 3e-4     #Initial learning rate for the optimizer. Adjust based on model size and batch size. Too high can cause divergence, too low can slow training.
T_LR_DECAY_STEP  = 40_000 #Number of steps after which to start decaying the learning rate. Helps with convergence in later stages of training.
T_LR_DECAYED     = 3e-5   #Final learning rate after decay. The learning rate will linearly decay from T_LR to T_LR_DECAYED starting at T_LR_DECAY_STEP until the end of training. This helps the model fine-tune its weights in later stages without overshooting minima.

GRAD_ACCUM_STEPS = 8 #8 Number of steps to accumulate gradients before performing an optimizer step. This effectively increases the batch size without increasing memory usage, which can help stabilize training and improve convergence, especially on smaller GPUs.
USE_AMP          = True #Whether to use Automatic Mixed Precision (AMP) for training. AMP can speed up training and reduce memory usage by using lower precision (float16) where possible, while maintaining model accuracy. This is especially beneficial on NVIDIA GPUs with Tensor Cores, like the RTX 4060.
COMPILE_MODEL    = False #Whether to use torch.compile() to optimize the model for faster training. This can provide significant speedups, but may introduce compatibility issues or bugs in some cases. It's recommended to test with and without this option to see if it benefits your specific setup and model architecture.

T_OUT_PATH = "models/transformer_rtx4060.pt"
DEVICE     = "cuda"

default_config = {
    'vocab_size':       VOCAB_SIZE,
    'context_length':   CONTEXT_LENGTH,
    'n_embed':          N_EMBED,
    'n_head':           N_HEAD,
    'n_blocks':         N_BLOCKS,
    'train_path':       TRAIN_PATH,
    'dev_path':         DEV_PATH,
    't_batch_size':     T_BATCH_SIZE,
    't_context_length': T_CONTEXT_LENGTH,
    't_train_steps':    T_TRAIN_STEPS,
    't_eval_steps':     T_EVAL_STEPS,
    't_eval_iters':     T_EVAL_ITERS,
    't_lr':             T_LR,
    't_lr_decay_step':  T_LR_DECAY_STEP,
    't_lr_decayed':     T_LR_DECAYED,
    'grad_accum_steps': GRAD_ACCUM_STEPS,
    'use_amp':          USE_AMP,
    'compile_model':    COMPILE_MODEL,
    't_out_path':       T_OUT_PATH,
    'device':           DEVICE,
}


