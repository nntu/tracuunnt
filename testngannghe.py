
post_scr = """
                 var table_html = ''
                $.post('tcnnt/nganhkinhdoanh.jsp', {tin: %s}, function(result){
                    table_html = result;
                });
                return table_html
                """ % (1800155565)
                
print(post_scr)