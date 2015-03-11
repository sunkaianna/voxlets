'''
Loads in the combined sboxes and clusters them to form a dictionary
smaller
'''
import numpy as np
import cPickle as pickle
import sys
import os
import yaml
from time import time
import scipy.io

sys.path.append(os.path.expanduser('~/projects/shape_sharing/src/'))
from common import paths
from common import voxel_data
from common import images
from common import parameters
from common import features
from common import carving
from common import voxlets

if not os.path.exists(paths.RenderedData.voxlets_dict_data_path):
    os.makedirs(paths.RenderedData.voxlets_dict_data_path)


def flatten_sbox(sbox):
    return sbox.V.flatten()


def process_sequence(sequence):

    print "Processing " + sequence['name']

    # load in the ground truth grid for this scene, and converting nans
    gt_vox = voxel_data.load_voxels(
        paths.RenderedData.ground_truth_voxels(sequence['scene']))
    gt_vox.V[np.isnan(gt_vox.V)] = -parameters.RenderedVoxelGrid.mu
    gt_vox.set_origin(gt_vox.origin)
    gt_vox.segment_project_2d(z_threshold=2, floor_height=4)

    # Move this into the voxel grid class?
    # gt_vox.label_grid(3) # returns a copy of the gt_vox but as if only label 3 exists...
    labels_grids = {}
    for idx in np.unique(gt_vox.labels):
        temp = gt_vox.copy()
        temp.V[gt_vox.labels != idx] = parameters.RenderedVoxelGrid.mu
        labels_grids[idx] = temp

    # loading this frame
    frame_data = paths.RenderedData.load_scene_data(
        sequence['scene'], sequence['frames'][0])
    im = images.RGBDImage.load_from_dict(
        paths.RenderedData.scene_dir(sequence['scene']), frame_data)
    im.label_from_grid(gt_vox)

    # computing normals...
    norm_engine = features.Normals()
    im.normals = norm_engine.compute_normals(im)

    "Sampling from image"
    idxs = im.random_sample_from_mask(
        parameters.VoxletTraining.pca_number_points_from_each_image)

    print "Performing voxel carving"
    video = images.RGBDVideo.init_from_images([im])
    carver = carving.Fusion()
    carver.set_video(video)
    carver.set_voxel_grid(gt_vox)
    im_tsdf, visible = carver.fuse(mu=parameters.RenderedVoxelGrid.mu)
    im_tsdf.V[np.isnan(im_tsdf.V)] = -parameters.RenderedVoxelGrid.mu
    im_tsdf.labels = gt_vox.labels

    "Now try to make this nice and like parrallel or something...?"
    t1 = time()
    gt_shoeboxes = [voxlets.extract_single_voxlet(
        idx, im, gt_vox, labels_grids, flatten_sbox) for idx in idxs]
    view_shoeboxes = [voxlets.extract_single_voxlet(
        idx, im, im_tsdf, labels_grids, flatten_sbox) for idx in idxs]
    print "Took %f s" % (time() - t1)

    np_gt_sboxes = np.array(gt_shoeboxes)
    np_view_sboxes = np.array(view_shoeboxes)

    print "Shoeboxes are shape " + str(np_gt_sboxes.shape)
    print "Features are shape " + str(np_view_sboxes.shape)

    D = dict(shoeboxes=np_gt_sboxes, features=np_view_sboxes)
    savepath = paths.RenderedData.voxlets_dict_data_path + \
        sequence['name'] + '.mat'
    print savepath
    scipy.io.savemat(savepath, D, do_compression=True)


# need to import these *after* the pool helper has been defined
if parameters.multicore:
    import multiprocessing
    import functools
    pool = multiprocessing.Pool(parameters.cores)
    mapper = pool.map
else:
    mapper = map


if __name__ == '__main__':

    tic = time()
    mapper(process_sequence, paths.RenderedData.train_sequence())
    print "In total took %f s" % (time() - tic)
