"""BIT change detection config for open-cd."""

_base_ = [
    "mmseg::_base_/default_runtime.py",
]

custom_imports = dict(imports=["opencd"], allow_failed_imports=False)

work_dir = "../artifacts/bit"
data_root = "../datasets/levir_cd"

crop_size = (256, 256)
train_pipeline = [
    dict(type="LoadImageFromFile"),
    dict(type="LoadAnnotations"),
    dict(type="RandomCrop", crop_size=crop_size, cat_max_ratio=0.75),
    dict(type="RandomFlip", prob=0.5),
    dict(type="PackSegInputs"),
]
test_pipeline = [
    dict(type="LoadImageFromFile"),
    dict(type="LoadAnnotations"),
    dict(type="PackSegInputs"),
]

dataset_type = "LEVIR_CD_Dataset"
data_prefix = dict(
    seg_map_path="label",
    img_path_from="A",
    img_path_to="B",
)

train_dataloader = dict(
    batch_size=2,
    num_workers=2,
    persistent_workers=True,
    sampler=dict(type="DefaultSampler", shuffle=True),
    dataset=dict(
        type=dataset_type,
        data_root=data_root,
        data_prefix=data_prefix,
        pipeline=train_pipeline,
        split="train",
    ),
)
val_dataloader = dict(
    batch_size=1,
    num_workers=2,
    persistent_workers=True,
    sampler=dict(type="DefaultSampler", shuffle=False),
    dataset=dict(
        type=dataset_type,
        data_root=data_root,
        data_prefix=data_prefix,
        pipeline=test_pipeline,
        split="test",
    ),
)
test_dataloader = val_dataloader

model = dict(
    type="DIEncoderDecoder",
    data_preprocessor=dict(
        type="DualInputSegDataPreProcessor",
        mean=[123.675, 116.28, 103.53] * 2,
        std=[58.395, 57.12, 57.375] * 2,
        bgr_to_rgb=True,
        size=crop_size,
        test_cfg=dict(size_divisor=32),
    ),
    backbone=dict(
        type="ResNet",
        depth=18,
        num_stages=4,
        out_indices=(0, 1, 2, 3),
        frozen_stages=-1,
        norm_cfg=dict(type="SyncBN", requires_grad=True),
        norm_eval=False,
        style="pytorch",
        init_cfg=dict(type="Pretrained", checkpoint="open-mmlab://resnet18_v1c"),
    ),
    decode_head=dict(
        type="BITHead",
        in_channels=[64, 128, 256, 512],
        in_index=[0, 1, 2, 3],
        channels=32,
        dropout_ratio=0.1,
        num_classes=2,
        norm_cfg=dict(type="SyncBN", requires_grad=True),
        align_corners=False,
        loss_decode=dict(type="CrossEntropyLoss", use_sigmoid=False, loss_weight=1.0),
    ),
    train_cfg=dict(),
    test_cfg=dict(mode="whole"),
)

optim_wrapper = dict(
    type="OptimWrapper",
    optimizer=dict(type="AdamW", lr=0.0001, weight_decay=0.05),
)
param_scheduler = [
    dict(type="PolyLR", eta_min=1e-6, power=0.9, begin=0, end=50, by_epoch=True),
]
train_cfg = dict(type="EpochBasedTrainLoop", max_epochs=50, val_interval=5)
val_cfg = dict(type="ValLoop")
test_cfg = dict(type="TestLoop")
val_evaluator = dict(type="IoUMetric", iou_metrics=["mFscore", "mIoU"])
test_evaluator = val_evaluator

default_hooks = dict(
    checkpoint=dict(type="CheckpointHook", interval=5, save_best="mFscore"),
)
