from sklearn.metrics import classification_report, confusion_matrix
def evaluate(y_true,y_pred): return {"report":classification_report(y_true,y_pred,output_dict=True,zero_division=0),"confusion_matrix":confusion_matrix(y_true,y_pred).tolist()}
