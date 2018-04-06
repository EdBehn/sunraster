'''
This module provides movie tools for level 2 IRIS SJI fits file
'''

from datetime import timedelta

from ndcube import NDCube
import numpy as np
from astropy.io import fits
import astropy.units as u
from astropy.wcs import WCS
from sunpy.time import parse_time
from sunpy import config
from irispy import iris_tools

__all__ = ['SJICube']

TIME_FORMAT = config.get("general", "time_format")

# the following value is only appropriate for byte scaled images
BAD_PIXEL_VALUE = -200
# the following value is only appropriate for unscaled images
BAD_PIXEL_VALUE_UNSCALED = -32768


class SJICube(NDCube):
    """
    SJICube

    Class representing SJI Images described by a single WCS

    Parameters
    ----------
    data: `numpy.ndarray`
        The array holding the actual data in this object.

    wcs: `ndcube.wcs.wcs.WCS`
        The WCS object containing the axes' information

    unit : `astropy.unit.Unit` or `str`
        Unit for the dataset.
        Strings that can be converted to a Unit are allowed.

    meta : dict-like object
        Additional meta information about the dataset.

    uncertainty : any type, optional
        Uncertainty in the dataset. Should have an attribute uncertainty_type
        that defines what kind of uncertainty is stored, for example "std"
        for standard deviation or "var" for variance. A metaclass defining
        such an interface is NDUncertainty - but isn’t mandatory. If the
        uncertainty has no such attribute the uncertainty is stored as
        UnknownUncertainty.
        Defaults to None.

    mask : any type, optional
        Mask for the dataset. Masks should follow the numpy convention
        that valid data points are marked by False and invalid ones with True.
        Defaults to None.

    extra_coords : iterable of `tuple`s, each with three entries
        (`str`, `int`, `astropy.units.quantity` or array-like)
        Gives the name, axis of data, and values of coordinates of a data axis
        not included in the WCS object.

    copy : `bool`, optional
        Indicates whether to save the arguments as copy. True copies every
        attribute before saving it while False tries to save every parameter
        as reference. Note however that it is not always possible to save the
        input as reference.
        Default is False.

    Examples
    --------
    >>> from irispy import sji
    >>> from irispy.data import sample
    >>> sji = read_iris_sji_level2_fits(sample.SJI_CUBE_1400)
    """

    def __repr__(self):
        return (
            """
    SJICube
    ---------
    Observatory:\t\t {obs}
    Instrument:\t\t\t {instrument}
    Bandpass:\t\t\t {bandpass}
    Obs. Start:\t\t\t {date_start:{tmf}}
    Obs. End:\t\t\t {date_end:{tmf}}
    Instance Start:\t\t {instance_start:{tmf}}
    Instance End:\t\t {instance_end:{tmf}}
    Total Frames in Obs.:\t {frame_num}
    IRIS Obs. id:\t\t {obs_id}
    IRIS Obs. Description:\t {obs_desc}
    Cube dimensions:\t\t {dimensions}
    Axis Types:\t\t\t {axis_types}
    """.format(obs=self.meta["TELESCOP"],
               instrument=self.meta["INSTRUME"],
               bandpass=self.meta["TWAVE1"],
               date_start=self.meta["DATE_OBS"],
               date_end=self.meta["DATE_END"],
               instance_start=self.extra_coords["TIME"]["value"][0],
               instance_end=self.extra_coords["TIME"]["value"][-1],
               frame_num=self.meta["NBFRAMES"],
               obs_id=self.meta["OBSID"],
               obs_desc=self.meta["OBS_DESC"],
               axis_types=self.world_axis_physical_types,
               dimensions=self.dimensions, tmf=TIME_FORMAT))


def read_iris_sji_level2_fits(filename):
    """
    Read IRIS level 2 SJI FITS from an OBS into an SJICube instance

    Parameters
    ----------
    filename : `str`
        File name to be read

    Returns
    -------
    result: 'irispy.sji.SJICube'

    """

    # Open a fits file
    my_file = fits.open(filename, memmap=True, do_not_scale_image_data=True)
    # Derive WCS, data and mask for NDCube from fits file.
    wcs = WCS(my_file[0].header)
    data = my_file[0].data
    data_nan_masked = my_file[0].data
    data_nan_masked[data == BAD_PIXEL_VALUE_UNSCALED] = BAD_PIXEL_VALUE
    mask = data_nan_masked == BAD_PIXEL_VALUE_UNSCALED
    # Derive unit and readout noise from detector.
    exposure_times = my_file[1].data[:, my_file[1].header["EXPTIMES"]]
    unit = iris_tools.DN_UNIT["SJI"]
    readout_noise = iris_tools.READOUT_NOISE["SJI"]
    # Derive uncertainty of data for NDCube from fits file.
    uncertainty = u.Quantity(np.sqrt((data_nan_masked*unit).to(u.photon).value
                                     + readout_noise.to(u.photon).value**2),
                             unit=u.photon).to(unit).value
    # Derive extra coordinates for NDCube from fits file.
    times = np.array([parse_time(my_file[0].header["STARTOBS"])
                      + timedelta(seconds=s)
                      for s in my_file[1].data[:, my_file[1].header["TIME"]]])
    pztx = my_file[1].data[:, my_file[1].header["PZTX"]] * u.arcsec
    pzty = my_file[1].data[:, my_file[1].header["PZTY"]] * u.arcsec
    xcenix = my_file[1].data[:, my_file[1].header["XCENIX"]] * u.arcsec
    ycenix = my_file[1].data[:, my_file[1].header["YCENIX"]] * u.arcsec
    obs_vrix = my_file[1].data[:, my_file[1].header["OBS_VRIX"]] * u.m/u.s
    ophaseix = my_file[1].data[:, my_file[1].header["OPHASEIX"]]
    extra_coords = [('TIME', 0, times), ("PZTX", 0, pztx), ("PZTY", 0, pzty),
                    ("XCENIX", 0, xcenix), ("YCENIX", 0, ycenix),
                    ("OBS_VRIX", 0, obs_vrix), ("OPHASEIX", 0, ophaseix),
                    ("EXPOSURE TIME", 0, exposure_times)]
    # Extraction of meta for NDCube from fits file.
    date_obs = my_file[0].header.get('DATE_OBS', None)
    date_obs = parse_time(date_obs) if date_obs else None
    date_end = my_file[0].header.get('DATE_END', None)
    date_end = parse_time(date_end) if date_end else None
    startobs = my_file[0].header.get('STARTOBS', None)
    startobs = parse_time(startobs) if startobs else None
    endobs = my_file[0].header.get('ENDOBS', None)
    endobs = parse_time(endobs) if endobs else None
    meta = {'TELESCOP': my_file[0].header.get('TELESCOP', "Unknown"),
            'INSTRUME': my_file[0].header.get('INSTRUME', "Unknown"),
            'TWAVE1': my_file[0].header.get('TWAVE1', "Unknown"),
            'DATE_OBS': date_obs,
            'DATE_END': date_end,
            'STARTOBS': startobs,
            'ENDOBS': endobs,
            'NBFRAMES': my_file[0].data.shape[0],
            'OBSID': my_file[0].header.get('OBSID', "Unknown"),
            'OBS_DESC': my_file[0].header.get('OBS_DESC', "Unknown")}

    my_file.close()

    return SJICube(data_nan_masked, wcs, uncertainty=uncertainty, unit=unit,
                   meta=meta, mask=mask, extra_coords=extra_coords)
