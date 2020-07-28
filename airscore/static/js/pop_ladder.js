
//function getData(ladderid, season) {
//    $.ajax({
//        type: "POST",
//        url: '/_get_ladder_result/'+ladderid+'/'+season,
//        contentType:"application/json",
//        dataType: "json",
//        success: json
//    });
//}

function populate_ladder(ladderid, season){
    $(document).ready(function() {
        $.ajax({
            type: "POST",
            url: '/_get_ladder_result/'+ladderid+'/'+season,
            contentType:"application/json",
            dataType: "json",
            success: function (json) {
                var taskNum = json.stats.valid_tasks
                console.log('taskNum='+taskNum);
                //    columnNames = Object.keys(data.data[0]);
                var columns = [];
                columns.push({data: 'ranks.rank', title:'#'});
                columns.push({data: 'ranks.class1', title:'#', defaultContent: ''});
                columns.push({data: 'ranks.class2', title:'#', defaultContent: ''});
                columns.push({data: 'ranks.class3', title:'#', defaultContent: ''});
                columns.push({data: 'ranks.class4', title:'#', defaultContent: ''});
                columns.push({data: 'fai_id', title:'FAI'});
                columns.push({data: 'civl_id', title:'CIVL'});
                columns.push({data: 'name', title:'Name'});
                columns.push({data: 'nat', title:'NAT'});
                columns.push({data: 'sex', title:'Sex'});
                columns.push({data: 'score', title:'Total'});
                for (var i=0; i<taskNum; i++ ) {
                    var col = (i+1)
                    columns.push({data: 'results.'+i.toString(), title: col.toString(), defaultContent: ''});
                }
                $('#results_table').DataTable( {
                    data: json.data,
                    paging: false,
                    searching: true,
                    saveState: true,
                    info: false,
                    "dom": 'lrtip',
                    columns: columns,
                    rowId: function(data) {
                            return 'id_' + data.par_id;
                    },
                    columnDefs: [
                        {
                            targets: [ 1, 2, 3, 4, 5, 6, 8, 9 ],
                            visible: false
                        },
                    ],
                    initComplete: function(settings) {
                        var table = $('#results_table');
                        var rows = $("tr", table).length-1;
                        // Get number of all columns
                        var numCols = table.DataTable().columns().nodes().length;
                        console.log('numCols='+numCols);

                        // comp info
                        $('#comp_name').text(json.info.ladder_name);
                        $('#comp_date').text(json.info.season);
                        if (json.info.ladder_class != "PG") {
                            update_classes(json.info.ladder_class);
                        }

                        // some GAP parameters
                        $('#formula tbody').append(
                                    "<tr><td>Overall Scoring</td><td>" + json.formula.overall_validity + ' (' + json.formula.validity_param + ')</td></tr>');
                        if (json.formula.overall_validity == 'ftv') {
                            $('#formula tbody').append(
                                    "<tr><td>Total Validity</td><td>" + json.stats.total_validity + '</td></tr>');
                        }

                        // remove empty cols
                        for ( var i=1; i<numCols; i++ ) {
                            var empty = true;
                            table.DataTable().column(i).data().each( function (e, i) {
                                if (e != "") {
                                    empty = false;
                                    return false;
                                }
                            } );

                            if (empty) {
                                table.DataTable().column( i ).visible( false );
                            }
                        }
                        // class picker
                        $("#dhv option").remove(); // Remove all <option> child tags.
                        // at the moment we provide the highest EN rating for a class and the overall_class_filter.js uses this.
                        // if we want to be more specific and pass a list of all EN ratings inside a class we can do something like this: https://stackoverflow.com/questions/15759863/get-array-values-from-an-option-select-with-javascript-to-populate-text-fields
                        $.each(json.classes, function(index, item) {
                            $("#dhv").append(
                                $("<option></option>")
                                    .text(item.name)
                                    .val(item.limit)
                            );
                        });
                    }
                });
            }
        });
    });
}
