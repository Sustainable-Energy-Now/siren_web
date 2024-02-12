from celery import shared_task

@shared_task(bind=True)
def run_powermatch_task(self, settings, constraints, generators, load_year, option, pmss_details, pmss_data, re_order, dispatch_order, pm_data_file, data_file):
    ex = pm.powerMatch(settings=settings, constraints=constraints, generators=generators)
    df_message = ex.doDispatch(load_year, option, pmss_details, pmss_data, re_order, dispatch_order, pm_data_file, data_file, title=None)
    return df_message